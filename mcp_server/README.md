# Campus Customs MCP Server

A FastMCP server that gives the agent team standard tools for the shop's data,
both lookups and safe store updates. Agents ask the server for facts instead of touching the database
themselves, so every answer comes from real rows and nothing is made up.

**Database:** `data/campus_customs_new.db` (the working copy, set in
`common/config.py`). The original `data/campus_customs.db` is never opened.
Reset the working copy with `python3 scripts/reset_db.py`. Lookups open the
database read-only; updates run in one transaction per call.

## Tools

Reads open the database read-only; a missing row returns `found: false`.

| Tool | Table(s) | Purpose |
|---|---|---|
| `get_today()` | `desk` | The shop's date. |
| `list_tickets()` | `tickets` | All tickets, open or resolved. |
| `list_open_tickets()` | `tickets` | Tickets not yet resolved. |
| `get_ticket(ticket_id)` | `tickets` | One ticket. |
| `check_stock(sku, size)` | `inventory` | Units on hand and aisle for one SKU and size. |
| `list_inventory(sku?)` | `inventory` | All sizes, optionally for one SKU. |
| `get_lease(lease_id)` | `leases` (+ `desk`) | Rent, landlord, due date and days until due. |
| `get_pricing(sku)` | `pricing` | Unit cost, list price and margin. |
| `check_discount(sku, discounted_price)` | `pricing` | Margin at a proposed price. |
| `list_vendors()` | `vendors`, `invoices` | Specialty, lead days, `can_ship`. |
| `list_invoices(status?, overdue_only?)` | `invoices` (+ `desk`) | Invoices with days overdue. |
| `get_cash_balance(account)` | `cash_accounts`, `payment_requests` | Balance and amount already promised. |
| `list_payments()` | `payments` | Payments actually made. |
| `list_payment_requests(status?)` | `payment_requests` | Requests awaiting or past a human decision. |
| `list_restock_requests()` | `restock_requests` | Restock proposals. |
| `list_message_drafts(ticket_id?)` | `message_drafts` | Saved customer drafts. |
| `list_price_proposals(ticket_id?)` | `price_proposals` | Discount proposals awaiting a human. |

Store updates (one transaction each; nothing is sent, paid or ordered):

| Tool | Writes | Purpose |
|---|---|---|
| `create_restock_request(ticket_id, sku, size, qty, vendor_id)` | `restock_requests` | Records a proposal; blocked while the vendor has an unpaid invoice. |
| `request_payment(kind, ref_id, amount, ticket_id, reason, requested_by)` | `payment_requests` | Asks a human to approve an invoice or rent payment; refuses duplicates and overdrafts. |
| `draft_customer_message(ticket_id, recipient, subject, body)` | `message_drafts` | Saves a reply as a draft; never sent. |
| `propose_price_override(ticket_id, sku, proposed_price, qty, rationale)` | `price_proposals` | Saves a discount proposal for a human; `pricing` is untouched. |
| `update_ticket(ticket_id, status, note)` | `tickets` | Sets status and appends a note; cannot resolve while approvals are pending. |

Human-only (no agent has them; the server refuses them unless launched by
`scripts/approve_payment.py`):

| Tool | Writes | Purpose |
|---|---|---|
| `approve_payment(request_id, approved_by)` | `payments`, `cash_accounts`, `invoices`, `payment_requests` | Executes a request: records the payment and approver, lowers cash, marks an invoice paid and releases that vendor's blocked restocks. |
| `reject_payment(request_id, decided_by)` | `payment_requests` | Rejects a pending request. |
| `approve_price_proposal(proposal_id, approved_by)` | `price_proposals` | Approves a pending discount proposal; `pricing` is untouched. |
| `reject_price_proposal(proposal_id, decided_by)` | `price_proposals` | Rejects a pending discount proposal. |

The tables `payment_requests`, `restock_requests`, `message_drafts` and
`price_proposals` are created by the server in the working database and are
cleared by `scripts/reset_db.py`.

## Run and test

```bash
.venv/bin/python -m mcp_server.server      # start the server (stdio)
.venv/bin/python scripts/test_mcp.py       # call every tool through a client
.venv/bin/python scripts/approve_payment.py list     # human approval of payments
```
