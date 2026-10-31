"""Campus Customs MCP server (FastMCP) over data/campus_customs_new.db.

Every fact the agents read and every store update they make goes through these
tools. Reads open the database read-only; writes go through `_write`, which
uses one transaction per call. Nothing here sends a message, calls a vendor or
moves money without a human: customer replies are saved as drafts, vendor
restocks are saved as proposals, and payments are saved as requests that only
a human can execute (see `approve_payment`).

Run:  .venv/bin/python -m mcp_server.server
"""
import os
import sqlite3
from contextlib import closing
from datetime import date, timedelta

from fastmcp import FastMCP

from common.config import DB_PATH

mcp = FastMCP("campus-customs")

TICKET_STATUSES = ("open", "in_progress", "waiting_approval", "resolved")
HUMAN_ONLY_ENV = "CC_HUMAN_APPROVER"  # set only by scripts/approve_payment.py

# Tables the agents' actions land in. They are created here (not in the
# original database) so scripts/reset_db.py wipes them with everything else.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS payment_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    ref_id INTEGER NOT NULL,
    covers TEXT,
    amount REAL NOT NULL,
    account TEXT NOT NULL,
    ticket_id INTEGER,
    reason TEXT,
    status TEXT NOT NULL DEFAULT 'pending_human_approval',
    requested_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    decided_by TEXT,
    decided_at TEXT,
    payment_id INTEGER
);
CREATE TABLE IF NOT EXISTS restock_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER,
    sku TEXT NOT NULL,
    size TEXT NOT NULL,
    qty INTEGER NOT NULL,
    vendor_id INTEGER NOT NULL,
    expected_arrival TEXT NOT NULL,
    status TEXT NOT NULL,
    blocked_by_invoice_id INTEGER,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS message_drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS price_proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    sku TEXT NOT NULL,
    qty INTEGER,
    list_price REAL NOT NULL,
    proposed_price REAL NOT NULL,
    margin_pct REAL NOT NULL,
    rationale TEXT,
    status TEXT NOT NULL DEFAULT 'pending_human_approval',
    created_at TEXT NOT NULL
);
"""


def _query(sql: str, params: tuple = ()) -> list[dict]:
    """Run a read-only query against the working database."""
    with closing(sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)) as con:
        con.row_factory = sqlite3.Row
        return [dict(r) for r in con.execute(sql, params).fetchall()]


def _write(fn):
    """Run fn(con) in one transaction on the working database; roll back on error."""
    with closing(sqlite3.connect(DB_PATH, isolation_level=None)) as con:
        con.row_factory = sqlite3.Row
        con.executescript(_SCHEMA)
        try:
            con.execute("BEGIN IMMEDIATE")
            result = fn(con)
            con.execute("COMMIT")
            return result
        except Exception:
            con.execute("ROLLBACK")
            raise


def _today() -> str:
    return _query("SELECT date_today FROM desk")[0]["date_today"]


def _stamp() -> str:
    return f"{_today()}T00:00:00"  # shop time comes from desk.date_today, not the clock


def _rows(table: str, where: str = "", params: tuple = ()) -> list[dict]:
    """Read an action table, creating it empty if nothing has been written yet."""
    with closing(sqlite3.connect(DB_PATH)) as con:
        con.executescript(_SCHEMA)
    return _query(f"SELECT * FROM {table} {where} ORDER BY id", params)


# --------------------------------------------------------------------------
# Reads
# --------------------------------------------------------------------------
@mcp.tool
def get_today() -> dict:
    """Return the shop's current date (table: desk). Never use the system clock."""
    return {"today": _today()}


@mcp.tool
def list_tickets() -> list[dict]:
    """List all tickets, open or resolved (table: tickets)."""
    return _query("SELECT * FROM tickets ORDER BY id")


@mcp.tool
def list_open_tickets() -> list[dict]:
    """List every ticket whose status is not 'resolved' (table: tickets)."""
    return _query("SELECT * FROM tickets WHERE status != 'resolved' ORDER BY id")


@mcp.tool
def get_ticket(ticket_id: int) -> dict:
    """Look up one ticket with all its fields (table: tickets)."""
    rows = _query("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    return {"found": True, **rows[0]} if rows else {"found": False, "ticket_id": ticket_id}


@mcp.tool
def check_stock(sku: str, size: str) -> dict:
    """Look up units on hand for one SKU and size (table: inventory).

    Returns the row's name, size, qty and location, or found=false when that
    SKU/size pair does not exist.
    """
    rows = _query(
        "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?",
        (sku.strip().upper(), size.strip().upper()),
    )
    if not rows:
        return {"found": False, "sku": sku, "size": size}
    return {"found": True, **rows[0]}


@mcp.tool
def list_inventory(sku: str | None = None) -> list[dict]:
    """List inventory rows, optionally for one SKU (table: inventory)."""
    if sku:
        return _query("SELECT * FROM inventory WHERE sku = ? ORDER BY size", (sku.strip().upper(),))
    return _query("SELECT * FROM inventory ORDER BY sku, size")


@mcp.tool
def get_lease(lease_id: int) -> dict:
    """Look up one lease and how soon rent is due (table: leases).

    Returns space, landlord, monthly_rent, next_due, today (desk.date_today)
    and days_until_due (negative means overdue).
    """
    rows = _query(
        "SELECT id, space_name, landlord, monthly_rent, next_due, notes FROM leases WHERE id = ?",
        (lease_id,),
    )
    if not rows:
        return {"found": False, "lease_id": lease_id}
    lease = rows[0]
    today = _today()
    days = (date.fromisoformat(lease["next_due"]) - date.fromisoformat(today)).days
    return {"found": True, **lease, "today": today, "days_until_due": days}


@mcp.tool
def get_pricing(sku: str) -> dict:
    """Look up unit cost, list price and margin for one SKU (table: pricing).

    margin_per_unit and margin_pct are calculated from the two stored prices.
    """
    rows = _query(
        "SELECT sku, unit_cost, list_price FROM pricing WHERE sku = ?",
        (sku.strip().upper(),),
    )
    if not rows:
        return {"found": False, "sku": sku}
    p = rows[0]
    margin = p["list_price"] - p["unit_cost"]
    return {
        "found": True,
        **p,
        "margin_per_unit": round(margin, 2),
        "margin_pct": round(margin / p["list_price"] * 100, 1),
    }


@mcp.tool
def check_discount(sku: str, discounted_price: float) -> dict:
    """Margin at a proposed per-unit price for one SKU (table: pricing). Read-only.

    Returns unit_cost, list_price, discount_pct off list, and margin_pct at the
    proposed price. below_cost is true when the price loses money.
    """
    if discounted_price <= 0:
        return {"found": False, "error": "discounted_price must be greater than 0"}
    rows = _query("SELECT * FROM pricing WHERE sku = ?", (sku.strip().upper(),))
    if not rows:
        return {"found": False, "sku": sku}
    p = rows[0]
    return {
        "found": True,
        "sku": p["sku"],
        "unit_cost": p["unit_cost"],
        "list_price": p["list_price"],
        "proposed_price": discounted_price,
        "discount_pct": round((1 - discounted_price / p["list_price"]) * 100, 1),
        "margin_per_unit": round(discounted_price - p["unit_cost"], 2),
        "margin_pct": round((discounted_price - p["unit_cost"]) / discounted_price * 100, 1),
        "below_cost": discounted_price < p["unit_cost"],
    }


@mcp.tool
def list_vendors() -> list[dict]:
    """List vendors with specialty and lead_days, plus whether each can ship.

    can_ship is false while the vendor has an open (unpaid) invoice (tables:
    vendors, invoices).
    """
    out = []
    for v in _query("SELECT * FROM vendors ORDER BY id"):
        unpaid = _query(
            "SELECT id, amount, due_date FROM invoices WHERE vendor_id = ? AND status = 'open'",
            (v["id"],),
        )
        out.append({**v, "can_ship": not unpaid, "open_invoices": unpaid})
    return out


@mcp.tool
def list_invoices(status: str | None = None, overdue_only: bool = False) -> list[dict]:
    """List invoices, optionally by status; overdue_only keeps open invoices
    past due_date as of desk.date_today (tables: invoices, desk).
    """
    today = _today()
    sql, params = "SELECT * FROM invoices", ()
    if status:
        sql, params = sql + " WHERE status = ?", (status,)
    out = []
    for inv in _query(sql + " ORDER BY id", params):
        days_overdue = (date.fromisoformat(today) - date.fromisoformat(inv["due_date"])).days
        inv["days_overdue"] = days_overdue if inv["status"] == "open" and days_overdue > 0 else 0
        if overdue_only and inv["days_overdue"] <= 0:
            continue
        out.append(inv)
    return out


@mcp.tool
def get_cash_balance(account: str = "checking") -> dict:
    """Balance of one cash account, plus money already promised in pending
    payment requests (tables: cash_accounts, payment_requests).
    """
    rows = _query("SELECT * FROM cash_accounts WHERE name = ?", (account,))
    if not rows:
        return {"found": False, "account": account}
    pending = sum(
        r["amount"]
        for r in _rows("payment_requests", "WHERE status = 'pending_human_approval' AND account = ?", (account,))
    )
    return {
        "found": True,
        **rows[0],
        "pending_requests_total": pending,
        "available_after_pending": round(rows[0]["balance"] - pending, 2),
    }


@mcp.tool
def list_payments() -> list[dict]:
    """List payments that have actually been made (table: payments)."""
    return _query("SELECT * FROM payments ORDER BY id")


@mcp.tool
def list_payment_requests(status: str | None = None) -> list[dict]:
    """List payment requests awaiting or past human decision (table: payment_requests)."""
    if status:
        return _rows("payment_requests", "WHERE status = ?", (status,))
    return _rows("payment_requests")


@mcp.tool
def list_restock_requests() -> list[dict]:
    """List restock proposals (table: restock_requests)."""
    return _rows("restock_requests")


@mcp.tool
def list_price_proposals(ticket_id: int | None = None) -> list[dict]:
    """List discount proposals awaiting a human (table: price_proposals)."""
    if ticket_id is not None:
        return _rows("price_proposals", "WHERE ticket_id = ?", (ticket_id,))
    return _rows("price_proposals")


@mcp.tool
def list_message_drafts(ticket_id: int | None = None) -> list[dict]:
    """List saved customer message drafts (table: message_drafts)."""
    if ticket_id is not None:
        return _rows("message_drafts", "WHERE ticket_id = ?", (ticket_id,))
    return _rows("message_drafts")


# --------------------------------------------------------------------------
# Store updates (execution tools)
# --------------------------------------------------------------------------
@mcp.tool
def create_restock_request(ticket_id: int, sku: str, size: str, qty: int, vendor_id: int) -> dict:
    """Propose restocking a SKU/size from a vendor (tables: inventory, vendors,
    invoices, restock_requests). Writes restock_requests only.

    This records a proposal; it never contacts the vendor. If the vendor has an
    open invoice the status is 'blocked_unpaid_invoice' and the invoice id is
    returned, otherwise 'proposed'. expected_arrival is desk.date_today plus
    the vendor's lead_days.
    """
    sku, size = sku.strip().upper(), size.strip().upper()
    if qty <= 0:
        return {"ok": False, "error": "qty must be positive"}

    def go(con):
        if not con.execute("SELECT 1 FROM inventory WHERE sku=? AND size=?", (sku, size)).fetchone():
            return {"ok": False, "error": f"unknown SKU/size {sku}/{size}"}
        vendor = con.execute("SELECT * FROM vendors WHERE id=?", (vendor_id,)).fetchone()
        if not vendor:
            return {"ok": False, "error": f"unknown vendor {vendor_id}"}
        unpaid = con.execute(
            "SELECT id FROM invoices WHERE vendor_id=? AND status='open' ORDER BY id", (vendor_id,)
        ).fetchone()
        arrival = (date.fromisoformat(_today()) + timedelta(days=vendor["lead_days"])).isoformat()
        status = "blocked_unpaid_invoice" if unpaid else "proposed"
        cur = con.execute(
            "INSERT INTO restock_requests (ticket_id, sku, size, qty, vendor_id, expected_arrival,"
            " status, blocked_by_invoice_id, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (ticket_id, sku, size, qty, vendor_id, arrival, status, unpaid["id"] if unpaid else None, _stamp()),
        )
        return {
            "ok": True,
            "restock_request_id": cur.lastrowid,
            "status": status,
            "vendor": vendor["name"],
            "expected_arrival_if_shipped_today": arrival,
            "blocked_by_invoice_id": unpaid["id"] if unpaid else None,
        }

    return _write(go)


@mcp.tool
def request_payment(kind: str, ref_id: int, amount: float, ticket_id: int, reason: str, requested_by: str) -> dict:
    """Ask for a payment to be approved by a human (tables: invoices, leases,
    cash_accounts, payment_requests). Writes payment_requests only; no money moves.

    kind is 'invoice' (ref_id = invoices.id) or 'rent' (ref_id = leases.id). The
    amount must equal the invoice amount or monthly rent. Refused when the
    invoice is not open, an identical request already exists, or the amount
    plus other pending requests would overdraw checking.
    """
    if kind not in ("invoice", "rent"):
        return {"ok": False, "error": "kind must be 'invoice' or 'rent'"}

    def go(con):
        if kind == "invoice":
            row = con.execute("SELECT * FROM invoices WHERE id=?", (ref_id,)).fetchone()
            if not row:
                return {"ok": False, "error": f"unknown invoice {ref_id}"}
            if row["status"] != "open":
                return {"ok": False, "error": f"invoice {ref_id} is {row['status']}, not open"}
            expected, covers = row["amount"], row["due_date"]
        else:
            row = con.execute("SELECT * FROM leases WHERE id=?", (ref_id,)).fetchone()
            if not row:
                return {"ok": False, "error": f"unknown lease {ref_id}"}
            expected, covers = row["monthly_rent"], row["next_due"]
        if round(amount, 2) != round(expected, 2):
            return {"ok": False, "error": f"amount must be {expected}"}
        dup = con.execute(
            "SELECT id FROM payment_requests WHERE kind=? AND ref_id=? AND covers=? AND status != 'rejected'",
            (kind, ref_id, covers),
        ).fetchone()
        if dup:
            return {"ok": False, "error": f"payment request {dup['id']} already exists for this item"}
        balance = con.execute("SELECT balance FROM cash_accounts WHERE name='checking'").fetchone()["balance"]
        pending = con.execute(
            "SELECT COALESCE(SUM(amount),0) FROM payment_requests"
            " WHERE status='pending_human_approval' AND account='checking'"
        ).fetchone()[0]
        if balance - pending - amount < 0:
            return {
                "ok": False,
                "error": "would overdraw checking",
                "balance": balance,
                "pending_requests_total": pending,
            }
        cur = con.execute(
            "INSERT INTO payment_requests (kind, ref_id, covers, amount, account, ticket_id, reason,"
            " requested_by, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (kind, ref_id, covers, amount, "checking", ticket_id, reason, requested_by, _stamp()),
        )
        return {
            "ok": True,
            "payment_request_id": cur.lastrowid,
            "status": "pending_human_approval",
            "balance_if_approved": round(balance - pending - amount, 2),
        }

    return _write(go)


@mcp.tool
def draft_customer_message(ticket_id: int, recipient: str, subject: str, body: str) -> dict:
    """Save a reply to a customer as a draft on the board (tables: tickets,
    message_drafts). Writes message_drafts only; it is never sent. There is no
    send tool.
    """
    if not (recipient.strip() and subject.strip() and body.strip()):
        return {"ok": False, "error": "recipient, subject and body are all required"}

    def go(con):
        if not con.execute("SELECT 1 FROM tickets WHERE id=?", (ticket_id,)).fetchone():
            return {"ok": False, "error": f"unknown ticket {ticket_id}"}
        cur = con.execute(
            "INSERT INTO message_drafts (ticket_id, recipient, subject, body, created_at) VALUES (?,?,?,?,?)",
            (ticket_id, recipient, subject, body, _stamp()),
        )
        return {"ok": True, "draft_id": cur.lastrowid, "status": "draft", "sent": False}

    return _write(go)


@mcp.tool
def propose_price_override(ticket_id: int, sku: str, proposed_price: float, qty: int, rationale: str) -> dict:
    """Propose a discounted per-unit price for human approval (tables: pricing,
    price_proposals). Writes price_proposals only; the pricing table is never
    changed. Refused when the price is at or below unit cost.
    """

    if qty <= 0:
        return {"ok": False, "error": "qty must be positive"}

    def go(con):
        p = con.execute("SELECT * FROM pricing WHERE sku=?", (sku.strip().upper(),)).fetchone()
        if not p:
            return {"ok": False, "error": f"unknown SKU {sku}"}
        if proposed_price <= p["unit_cost"]:
            return {"ok": False, "error": f"price must be above unit cost {p['unit_cost']}"}
        if proposed_price > p["list_price"]:
            return {"ok": False, "error": f"price is above list price {p['list_price']}"}
        margin = round((proposed_price - p["unit_cost"]) / proposed_price * 100, 1)
        cur = con.execute(
            "INSERT INTO price_proposals (ticket_id, sku, qty, list_price, proposed_price, margin_pct,"
            " rationale, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (ticket_id, p["sku"], qty, p["list_price"], proposed_price, margin, rationale, _stamp()),
        )
        return {"ok": True, "price_proposal_id": cur.lastrowid, "status": "pending_human_approval", "margin_pct": margin}

    return _write(go)


@mcp.tool
def update_ticket(ticket_id: int, status: str, note: str) -> dict:
    """Set a ticket's status and append a note (table: tickets).

    status is one of open, in_progress, waiting_approval, resolved. A ticket
    cannot be 'resolved' while a payment request or price proposal tied to it
    is still pending human approval.
    """
    if status not in TICKET_STATUSES:
        return {"ok": False, "error": f"status must be one of {TICKET_STATUSES}"}

    def go(con):
        t = con.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
        if not t:
            return {"ok": False, "error": f"unknown ticket {ticket_id}"}
        if status == "resolved":
            waiting = con.execute(
                "SELECT (SELECT COUNT(*) FROM payment_requests WHERE ticket_id=? AND status='pending_human_approval')"
                " + (SELECT COUNT(*) FROM price_proposals WHERE ticket_id=? AND status='pending_human_approval')",
                (ticket_id, ticket_id),
            ).fetchone()[0]
            if waiting:
                return {"ok": False, "error": f"{waiting} item(s) still await human approval; use waiting_approval"}
        merged = f"{t['notes'] or ''}\n[{_today()}] {note}".strip()
        con.execute("UPDATE tickets SET status=?, notes=? WHERE id=?", (status, merged, ticket_id))
        return {"ok": True, "ticket_id": ticket_id, "status": status}

    return _write(go)


# --------------------------------------------------------------------------
# Human-only: agents are never given these tools, and the server refuses them
# unless it was launched by scripts/approve_payment.py (CC_HUMAN_APPROVER set).
# --------------------------------------------------------------------------
def _human_guard(approved_by: str) -> str | None:
    if not os.environ.get(HUMAN_ONLY_ENV):
        return "payments can only be decided by a human through scripts/approve_payment.py"
    if not approved_by.strip():
        return "approved_by (the human's name) is required"
    return None


@mcp.tool
def approve_payment(request_id: int, approved_by: str) -> dict:
    """HUMAN ONLY. Execute an approved payment request (tables: payment_requests,
    payments, cash_accounts, invoices). Writes a payments row, lowers the cash
    balance, and marks an invoice 'paid', all in one transaction. Refuses if
    the balance would go negative.
    """
    if err := _human_guard(approved_by):
        return {"ok": False, "error": err}

    def go(con):
        req = con.execute("SELECT * FROM payment_requests WHERE id=?", (request_id,)).fetchone()
        if not req:
            return {"ok": False, "error": f"unknown payment request {request_id}"}
        if req["status"] != "pending_human_approval":
            return {"ok": False, "error": f"request is {req['status']}"}
        bal = con.execute("SELECT balance FROM cash_accounts WHERE name=?", (req["account"],)).fetchone()["balance"]
        if bal - req["amount"] < 0:
            return {"ok": False, "error": "would overdraw the account", "balance": bal}
        cur = con.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?,?,?,?,?,?)",
            (req["kind"], req["ref_id"], req["amount"], req["account"], _stamp(), approved_by.strip()),
        )
        con.execute("UPDATE cash_accounts SET balance = balance - ? WHERE name=?", (req["amount"], req["account"]))
        if req["kind"] == "invoice":
            con.execute("UPDATE invoices SET status='paid' WHERE id=?", (req["ref_id"],))
            # The vendor can ship again once nothing else is unpaid: release its blocked restock proposals.
            vendor_id = con.execute("SELECT vendor_id FROM invoices WHERE id=?", (req["ref_id"],)).fetchone()["vendor_id"]
            if not con.execute("SELECT 1 FROM invoices WHERE vendor_id=? AND status='open'", (vendor_id,)).fetchone():
                con.execute(
                    "UPDATE restock_requests SET status='proposed', blocked_by_invoice_id=NULL"
                    " WHERE vendor_id=? AND status='blocked_unpaid_invoice'",
                    (vendor_id,),
                )
        con.execute(
            "UPDATE payment_requests SET status='approved', decided_by=?, decided_at=?, payment_id=? WHERE id=?",
            (approved_by.strip(), _stamp(), cur.lastrowid, request_id),
        )
        return {"ok": True, "payment_id": cur.lastrowid, "new_balance": round(bal - req["amount"], 2)}

    return _write(go)


@mcp.tool
def reject_payment(request_id: int, decided_by: str) -> dict:
    """HUMAN ONLY. Reject a pending payment request (table: payment_requests)."""
    if err := _human_guard(decided_by):
        return {"ok": False, "error": err}

    def go(con):
        n = con.execute(
            "UPDATE payment_requests SET status='rejected', decided_by=?, decided_at=?"
            " WHERE id=? AND status='pending_human_approval'",
            (decided_by.strip(), _stamp(), request_id),
        ).rowcount
        return {"ok": True, "status": "rejected"} if n else {"ok": False, "error": "no pending request with that id"}

    return _write(go)


def _decide_proposal(proposal_id: int, who: str, status: str) -> dict:
    if err := _human_guard(who):
        return {"ok": False, "error": err}

    def go(con):
        n = con.execute(
            "UPDATE price_proposals SET status=? WHERE id=? AND status='pending_human_approval'",
            (status, proposal_id),
        ).rowcount
        return {"ok": True, "price_proposal_id": proposal_id, "status": status, "decided_by": who.strip()} if n else {
            "ok": False, "error": "no pending price proposal with that id"}

    return _write(go)


@mcp.tool
def approve_price_proposal(proposal_id: int, approved_by: str) -> dict:
    """HUMAN ONLY. Approve a pending discount proposal (table: price_proposals).
    The pricing table itself is never changed.
    """
    return _decide_proposal(proposal_id, approved_by, "approved")


@mcp.tool
def reject_price_proposal(proposal_id: int, decided_by: str) -> dict:
    """HUMAN ONLY. Reject a pending discount proposal (table: price_proposals)."""
    return _decide_proposal(proposal_id, decided_by, "rejected")


if __name__ == "__main__":
    mcp.run()
