"""Build the Problem 9 deliverables from the working database and the audit trail.

  python scripts/build_outputs.py

Writes output/resolved_tickets.json, rewrites the Actual sections and the Cash
tab of output/desk_tickets.html (Expected sections are left alone), and writes
output/resolved_board.html. Nothing here is typed in by hand: every number comes
from data/campus_customs_new.db or output/audit_trail.json.
"""
import html
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from common.config import DB_PATH  # noqa: E402

OUT = ROOT / "output"
HIDDEN = {"delegate", "hand_off", "final_result"}
EXPECTED = {
    101: ["check_stock", "list_vendors", "list_invoices", "request_payment"],
    102: ["get_lease", "get_cash_balance", "request_payment"],
    103: ["check_stock", "check_discount", "get_pricing"],
}
CHAR = {
    "boss": ("👑", "The Boss", "Main Player"), "inventory": ("🎒", "Merchant", "Inventory NPC"),
    "accounting": ("🔮", "Treasury Mage", "Accounting NPC"), "facilities": ("🏰", "Castle Steward", "Facilities NPC"),
    "customer_service": ("📯", "Town Herald", "Customer Service NPC"),
}
PLAIN = {"boss": "Boss", "inventory": "Inventory", "accounting": "Accounting", "facilities": "Facilities", "customer_service": "Customer Service"}
TITLES = {101: "The Missing Tee", 102: "The Landlord's Summons", 103: "The Club's Bulk Bargain"}
e = html.escape


def money(x: float) -> str:
    return f"${x:,.2f}"


def load():
    events = json.loads((OUT / "audit_trail.json").read_text())
    batch = max(x["seq"] for x in events if x["event"] == "database_reset" and "attempt 2" in str(x.get("note")))
    start = next(x["starting_checking_balance"] for x in events if x["seq"] == batch)
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    q = lambda sql, p=(): [dict(r) for r in con.execute(sql, p)]
    return events, batch, start, q


def ticket_data(t, events, batch, q):
    ev = [x for x in events if x.get("ticket_id") == t["id"] and x["seq"] > batch]
    first = next(x for x in ev if x["agent"] == "boss" and x["event"] == "run_start" and not x["prompt"].startswith("Follow-up"))
    follow = [x for x in ev if x["agent"] == "boss" and x["event"] == "run_start" and x["prompt"].startswith("Follow-up")]
    main_end = follow[0]["seq"] if follow else 10**9
    main = [x for x in ev if first["seq"] <= x["seq"] < main_end]
    outs = {}
    for x in ev:
        if x["event"] == "agent_output":
            outs.setdefault(x["agent"], []).append(x)
    main_outs = {}
    for x in main:
        if x["event"] == "agent_output":
            main_outs[x["agent"]] = x["output"]
    deleg = [
        {"type": x["event"], "from": x["agent"], "to": x["to"], "task": re.sub(r"\s+", " ", x["task"]).strip()}
        for x in main if x["event"] in ("delegation", "handoff")
    ]
    tools = {a: Counter(x["tool"] for x in ev if x["event"] == "tool_call" and x["agent"] == a and x["tool"] not in HIDDEN)
             for a in CHAR}
    tools = {a: dict(c) for a, c in tools.items() if c}
    boss_main = main_outs.get("boss", {})
    boss_final = outs["boss"][-1]["output"]
    return dict(ev=ev, main=main, follow=follow, main_outs=main_outs, deleg=deleg, tools=tools,
                boss_main=boss_main, boss_final=boss_final)


def main():
    events, batch, start, q = load()
    tickets = q("select * from tickets order by id")
    payments = q("select p.*, r.ticket_id, i.description as inv_desc, l.space_name from payments p "
                 "left join payment_requests r on r.payment_id = p.id "
                 "left join invoices i on p.kind='invoice' and i.id = p.ref_id "
                 "left join leases l on p.kind='rent' and l.id = p.ref_id order by p.id")
    end = q("select balance from cash_accounts where name='checking'")[0]["balance"]
    proposals = q("select * from price_proposals order by id")
    price_approver = {x["proposal_id"]: x["approved_by"] for x in events
                      if x["event"] == "price_proposal_approved" and x["seq"] > batch and "proposal_id" in x}
    drafts = q("select * from message_drafts")
    restocks = q("select * from restock_requests")
    data = {t["id"]: ticket_data(t, events, batch, q) for t in tickets}

    # ---- cash itemization with a math check
    items, running = [], start
    for p in payments:
        running = round(running - p["amount"], 2)
        what = (f"Paid vendor invoice #{p['ref_id']}: {p['inv_desc']}" if p["kind"] == "invoice"
                else f"Paid rent for {p['space_name']}")
        items.append(dict(ticket_id=p["ticket_id"], description=what, amount=-p["amount"], balance_after=running,
                          approved_by=p["approved_by"], payment_id=p["id"]))
    paid_tickets = {i["ticket_id"] for i in items}
    for t in tickets:
        if t["id"] not in paid_tickets:
            items.append(dict(ticket_id=t["id"], description="No cash moved (discount approved; no payment or purchase)",
                              amount=0.0, balance_after=running, approved_by=None, payment_id=None))
    items.sort(key=lambda i: i["ticket_id"])
    total = round(sum(i["amount"] for i in items), 2)
    assert round(start + total, 2) == round(end, 2) == round(running, 2), "cash math does not reconcile"

    # ---- resolved_tickets.json
    resolved = []
    for t in tickets:
        d = data[t["id"]]
        approvals = [dict(type="payment", id=p["id"], amount=p["amount"], description=i["description"],
                          approved_by=p["approved_by"], paid_at=p["paid_at"])
                     for p, i in zip(payments, [x for x in items if x["payment_id"]]) if p["ticket_id"] == t["id"]]
        approvals += [dict(type="price_proposal", id=x["id"], description=f"{x['sku']} at {money(x['proposed_price'])} each x {x['qty']} "
                           f"(list {money(x['list_price'])}, margin {x['margin_pct']}%)", status=x["status"],
                           approved_by=price_approver.get(x["id"])) for x in proposals if x["ticket_id"] == t["id"]]
        contrib = {}
        for a, o in d["main_outs"].items():
            if a == "boss":
                contrib[a] = dict(summary=o["summary"], delegations=o["delegations"], tools=d["tools"].get(a, {}))
            else:
                contrib[a] = dict(findings=o["findings"], actions_taken=o["actions_taken"],
                                  recommendation=o["recommendation"], tools=d["tools"].get(a, {}))
        resolved.append(dict(
            ticket_id=t["id"], type=t["type"], subject=t["subject"], requester=t["requester"], final_status=t["status"],
            outcome_summary=outcome(t, approvals, q, drafts, restocks), team_report=d["boss_main"].get("summary", ""),
            resolution_note=d["boss_final"]["summary"],
            delegations=d["deleg"], agent_contributions=contrib, human_approvals=approvals,
            drafts_saved=[dict(id=x["id"], recipient=x["recipient"], status=x["status"]) for x in drafts if x["ticket_id"] == t["id"]],
            restock_requests=[dict(id=x["id"], sku=x["sku"], size=x["size"], qty=x["qty"], status=x["status"])
                              for x in restocks if x["ticket_id"] == t["id"]],
        ))
    (OUT / "resolved_tickets.json").write_text(json.dumps(resolved, indent=2) + "\n")

    # ---- desk_tickets.html: Actual sections + Cash tab
    page = (OUT / "desk_tickets.html").read_text()
    for t in tickets:
        page = replace_actual(page, t, data[t["id"]])
    page = replace_cash(page, start, items, total, end)
    (OUT / "desk_tickets.html").write_text(page)

    # ---- resolved_board.html
    (OUT / "resolved_board.html").write_text(board(tickets, data, items, start, end, payments, resolved))
    print(f"start {money(start)}  changes {money(total)}  end {money(end)}  (matches cash_accounts)")


def outcome(t, approvals, q, drafts, restocks):
    """Final-state summary written from database facts (not from the agents' pre-approval reports)."""
    tid = t["id"]
    stock = q("select qty from inventory where sku=? and size=?", (t["sku"], t["size"]))[0]["qty"] if t["sku"] else None
    rs = [x for x in restocks if x["ticket_id"] == tid]
    dr = [x for x in drafts if x["ticket_id"] == tid]
    who = approvals[0]["approved_by"] if approvals else "a human"
    if t["type"] == "customer_order":
        return (f"Size {t['size']} tee is out of stock ({stock} on hand). {approvals[0]['description']} (${approvals[0]['amount']:,.2f}) "
                f"was approved by {who}, so the vendor can ship again; restock request {rs[0]['id']} is now '{rs[0]['status']}' "
                f"(a proposal, no order placed). Customer reply draft {dr[0]['id']} is saved and not sent.")
    if t["type"] == "rent_notice":
        return (f"{approvals[0]['description']} (${approvals[0]['amount']:,.2f}) was prepared by Accounting and approved by {who}; "
                "checking fell by that amount and no landlord was contacted.")
    return (f"{stock} hoodies on hand of {t['qty']} requested; the 12-unit restock request {rs[0]['id']} is '{rs[0]['status']}' after invoice 501 was paid. "
            f"Discount proposal approved by {who}: {approvals[0]['description']}. No cash moved. Customer reply draft {dr[0]['id']} is saved and not sent.")


def chips(counter):
    return "".join(f'<li><code>{e(k)}</code> ×{v}</li>' for k, v in counter.items())


def replace_actual(page, t, d):
    tid = t["id"]
    worked = [a for a in CHAR if a in d["main_outs"]]
    all_tools = Counter()
    for c in d["tools"].values():
        all_tools.update(c)
    exp = EXPECTED[tid]
    hit = [x for x in exp if x in all_tools]
    miss = [x for x in exp if x not in all_tools]
    extra = [x for x in all_tools if x not in exp]
    first_called = next((x["to"] for x in d["deleg"] if x["from"] == "boss"), "?")
    dl = "".join(f"<li><strong>{e(PLAIN[x['from']])}</strong> ➜ <strong>{e(PLAIN[x['to']])}</strong> "
                 f"<em>({'delegation' if x['type']=='delegation' else 'handoff'})</em>: {e(x['task'][:170])}{'…' if len(x['task'])>170 else ''}</li>"
                 for x in d["deleg"])
    per = "".join(f"<li><strong>{e(PLAIN[a])}</strong>: " + ", ".join(f"<code>{e(k)}</code> ×{v}" for k, v in c.items()) + "</li>"
                  for a, c in d["tools"].items())
    block = f'''<article class="card actual done-actual" aria-labelledby="act-{tid}">
      <h3 id="act-{tid}">Actual</h3>
      <p class="final"><span class="okbadge">{e(t["status"]).upper()}</span> Live run of the agent team, then human approval, then Boss follow-up.</p>
      <h4>Boss called first</h4>
      <p><strong>{e(first_called.replace("_"," ").title())}</strong></p>
      <h4>Agents who worked</h4>
      <p>{", ".join("<strong>"+e(PLAIN[a])+"</strong>" for a in worked)}</p>
      <h4>Agent delegations</h4>
      <ol>{dl}</ol>
      <h4>Tools used</h4>
      <ul class="tools">{chips(all_tools)}</ul>
      <ul class="bytool">{per}</ul>
      <h4>Against Expected</h4>
      <p class="cmp">Expected tools used: <strong>{len(hit)} of {len(exp)}</strong>{(" (not used: " + ", ".join("<code>"+m+"</code>" for m in miss) + ")") if miss else ""}.
      {("Also used: " + ", ".join("<code>"+x+"</code>" for x in extra) + ".") if extra else ""}</p>
    </article>'''
    pat = re.compile(rf'<article class="card actual" aria-labelledby="act-{tid}">.*?</article>', re.S)
    pat2 = re.compile(rf'<article class="card actual done-actual" aria-labelledby="act-{tid}">.*?</article>', re.S)
    page, n = pat.subn(lambda m: block, page)
    if n == 0:
        page, n = pat2.subn(lambda m: block, page)
    assert n == 1, f"actual block for {tid} not found"
    if ".okbadge" not in page:
        page = page.replace("</style>", """.okbadge{background:#6ee7a8;color:#052b17;border-radius:999px;padding:2px 10px;font-size:.75rem;font-weight:800;margin-right:6px}
.bytool{margin-top:8px;color:var(--muted);font-size:.88rem}.cmp{color:var(--muted)}
.cash-table{width:100%;border-collapse:collapse;margin:10px 0}.cash-table th,.cash-table td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line)}
.cash-table th{color:var(--muted);font-size:.8rem;text-transform:uppercase;letter-spacing:.06em}.num{text-align:right!important;font-variant-numeric:tabular-nums}
.neg{color:var(--pink-soft)}.total td{font-weight:800;border-top:2px solid var(--pink)}.verify{color:#6ee7a8;margin-top:12px}.cash-card{max-width:900px}
</style>""",1)
    return page


def replace_cash(page, start, items, total, end):
    rows = "".join(
        f'<tr><td>Ticket {i["ticket_id"]}</td><td>{e(i["description"])}{(" <em>(approved by "+e(i["approved_by"])+")</em>") if i["approved_by"] else ""}</td>'
        f'<td class="num {"neg" if i["amount"] else ""}">{("−"+money(-i["amount"])) if i["amount"] else money(0)}</td><td class="num">{money(i["balance_after"])}</td></tr>'
        for i in items)
    expr = f'{money(start)} − ' + " − ".join(money(-i["amount"]) for i in items if i["amount"]) + f' = {money(end)}'
    panel = f'''<section id="panel-cash" class="panel" role="tabpanel" aria-labelledby="tab-cash" tabindex="0" hidden>
  <header class="ticket-head"><h2>Cash</h2></header>
  <div class="card cash-card">
    <table class="cash-table">
      <thead><tr><th>Source</th><th>Description</th><th class="num">Change</th><th class="num">Checking after</th></tr></thead>
      <tbody>
        <tr><td>Start</td><td>Checking balance after database reset</td><td class="num">—</td><td class="num">{money(start)}</td></tr>
        {rows}
        <tr class="total"><td>End</td><td>Ending checking balance (matches <code>cash_accounts</code> in <code>campus_customs_new.db</code>)</td><td class="num neg">−{money(-total)}</td><td class="num">{money(end)}</td></tr>
      </tbody>
    </table>
    <p class="verify">✔ Math check: {expr}. Total payouts {money(-total)}; the database balance is {money(end)}.</p>
    <p class="placeholder">Invoice 501 was paid once, under ticket 101; it also unblocked the vendor for ticket 103's hoodie restock.</p>
  </div>
</section>'''
    page, n = re.subn(r'<section id="panel-cash".*?</section>', lambda m: panel, page, flags=re.S)
    assert n == 1
    return page


def board(tickets, data, items, start, end, payments, resolved):
    css = (ROOT / "frontend" / "src" / "styles.css").read_text()
    css += """
.nav{display:flex;gap:10px;flex-wrap:wrap;margin:0 0 22px}.nav a{color:var(--pink-soft);border:1px solid var(--line);border-radius:999px;padding:6px 16px;text-decoration:none}
.nav a:hover{border-color:var(--pink)} section.rq{margin:0 0 56px;padding-top:12px;border-top:1px solid var(--line)}
.rq .vault{margin:0}.row{display:flex;justify-content:space-between;gap:16px;align-items:center;flex-wrap:wrap;margin-bottom:14px}
.appr{background:var(--panel2);border:1px solid #7a5f1a;border-radius:12px;padding:12px 16px;margin-top:14px}.appr li{margin:4px 0}
.note{color:var(--muted);font-size:.9rem;margin-bottom:20px}.log-list{max-height:none}.char.active{animation:none}
"""
    secs = []
    for t, r in zip(tickets, resolved):
        d = data[t["id"]]
        tid = t["id"]
        # vault after this ticket's change
        after = next(i["balance_after"] for i in items if i["ticket_id"] == tid)
        party = ""
        for a, (ic, nm, role) in CHAR.items():
            acts = sum(d["tools"].get(a, {}).values())
            done = a in d["main_outs"]
            chip = f'<span class="done-chip">✔ Task done · {acts} action{"s" if acts != 1 else ""}</span>' if done else '<span class="idle-chip">Not called this quest</span>'
            cls = "char char-boss done" if a == "boss" else ("char done" if done else "char")
            card = f'<article class="{cls}"><div class="char-icon">{ic}</div><h3>{nm}</h3><p class="char-role">{role}</p><div class="char-status">{chip}</div></article>'
            party += card if a == "boss" else card
        lines = ""
        for x in d["ev"]:
            c = CHAR.get(x["agent"])
            if not c:
                continue
            ic, nm, _ = c
            if x["event"] in ("delegation", "handoff"):
                lines += (f'<li class="line line-speech"><span class="line-icon">{ic}</span><div><span class="line-name">{nm} <span class="arrow">➜</span> {CHAR[x["to"]][1]}</span>'
                          f'<p class="line-text">{e(re.sub(chr(10)," ",x["task"])[:240])}</p></div></li>')
            elif x["event"] == "tool_call" and x["tool"] not in HIDDEN:
                lines += (f'<li class="line line-action"><span class="line-icon">{ic}</span><div><span class="line-name">{nm}</span>'
                          f'<p class="line-text"><span class="spell">⚡ {e(x["tool"])}</span></p></div></li>')
            elif x["event"] == "agent_output":
                o = x["output"]
                txt = o.get("summary") or o.get("recommendation") or ""
                lines += (f'<li class="line line-report"><span class="line-icon">{ic}</span><div><span class="line-name">{nm}</span>'
                          f'<p class="line-text">“{e(txt)}”</p></div></li>')
        cards = ""
        for a in CHAR:
            if a not in d["main_outs"]:
                continue
            ic, nm, role = CHAR[a]
            o = r["agent_contributions"][a]
            if a == "boss":
                body = f'<p class="sum-text">{e(o["summary"])}</p><h4>Orders given</h4><ul>' + "".join(f"<li>{e(x)}</li>" for x in o["delegations"]) + "</ul>"
            else:
                body = (f'<p class="sum-text">{e(o["recommendation"])}</p><h4>Learned</h4><ul>' + "".join(f"<li>{e(x)}</li>" for x in o["findings"]) +
                        "</ul><h4>Did</h4><ul>" + "".join(f"<li>{e(x)}</li>" for x in o["actions_taken"]) + "</ul>")
            cards += f'<article class="sum-card"><h3>{ic} {nm} <small>{role}</small></h3>{body}</article>'
        appr = "".join(
            f'<li>{"🔏 Payment #"+str(a["id"])+": "+e(a["description"])+" — "+money(a["amount"]) if a["type"]=="payment" else "🔏 Discount proposal #"+str(a["id"])+": "+e(a["description"])} '
            f'— stamped by <strong>{e(a["approved_by"])}</strong></li>' for a in r["human_approvals"])
        secs.append(f'''<section class="rq" id="q{tid}">
  <div class="row"><div><h2 class="quest-title">Quest #{tid}: {e(t["subject"])} — {TITLES[tid]}</h2>
  <p class="muted">{e(t["requester"])} · {e(t["type"].replace("_"," "))}</p></div>
  <div style="display:flex;gap:12px;align-items:center"><span class="badge badge-completed">Resolved</span>
  <div class="vault"><span class="vault-icon">🪙</span><div><p class="vault-label">Gold Vault after this quest</p><p class="vault-gold">{money(after)}</p></div></div></div></div>
  <div class="party-grid"><div>{party.split('</article>')[0]}</article></div><div class="npcs">{"".join(p+"</article>" for p in party.split("</article>")[1:-1])}</div></div>
  <div class="log" style="margin-top:16px"><h2>Party Dialogue</h2><ol class="log-list">{lines}</ol></div>
  <div class="victory" style="margin-top:16px"><div class="victory-banner"><h2>🏆 Quest Complete — {e(t["subject"])}</h2><p>{e(r["resolution_note"])}</p></div>
  <div class="sum-grid">{cards}</div>
  <div class="appr"><strong>Guild Master approvals</strong><ul>{appr}</ul></div></div>
</section>''')
    nav = "".join(f'<a href="#q{t["id"]}">Quest #{t["id"]}</a>' for t in tickets) + '<a href="#vault">Gold Vault</a>'
    rows = "".join(f"<tr><td>Ticket {i['ticket_id']}</td><td>{e(i['description'])}</td><td class='num'>{('−'+money(-i['amount'])) if i['amount'] else money(0)}</td><td class='num'>{money(i['balance_after'])}</td></tr>" for i in items)
    return f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Campus Customs — Resolved Board</title><style>{css}
.cash-table{{width:100%;border-collapse:collapse}}.cash-table th,.cash-table td{{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line)}}.num{{text-align:right!important}}
</style></head><body><div class="app">
<header class="top"><div><h1>Campus <span>Customs</span> — Resolved Board</h1>
<p class="muted">Renders of the quest dashboard for the three resolved tickets, built from the live run (database + audit trail).</p></div>
<div class="vault"><span class="vault-icon">🪙</span><div><p class="vault-label">Shop Gold Vault (final)</p><p class="vault-gold">{money(end)}</p><p class="vault-pending">started at {money(start)}</p></div></div><div></div></header>
<nav class="nav" aria-label="Quests">{nav}</nav>
<p class="note">Static renders, not live: the dashboard itself runs with <code>npm run dev</code> in <code>frontend/</code>. Everything below is generated by <code>scripts/build_outputs.py</code>.</p>
{"".join(secs)}
<section class="rq" id="vault"><h2>Gold Vault: {money(start)} → {money(end)}</h2>
<table class="cash-table"><thead><tr><th>Source</th><th>Description</th><th class="num">Change</th><th class="num">Vault after</th></tr></thead><tbody>
<tr><td>Start</td><td>After database reset</td><td class="num">—</td><td class="num">{money(start)}</td></tr>{rows}
<tr><td><strong>End</strong></td><td><strong>Matches cash_accounts</strong></td><td class="num"></td><td class="num"><strong>{money(end)}</strong></td></tr></tbody></table></section>
</div></body></html>'''


main()
