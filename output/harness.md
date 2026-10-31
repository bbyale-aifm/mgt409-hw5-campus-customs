# Campus Customs Harness — Database Reference

Working database: `data/campus_customs_new.db` (a copy of `data/campus_customs.db`;
the original is never written to). Reset it with `python3 scripts/reset_db.py`
before every full ticket run. "Today" is always `desk.date_today`, never the
system clock.

## Tables

### `desk`
| Field | Type | Notes |
|---|---|---|
| `date_today` | TEXT | The shop's current date (`2026-08-31`). |
| `notes` | TEXT | Free-form notes (empty). |

**Why it matters:** Every date comparison (overdue invoices, days until rent,
vendor arrival dates) uses this value. All agents must read it instead of the
system clock, so results are repeatable.

### `tickets`
| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | Ticket number. |
| `type` | TEXT | `customer_order`, `rent_notice`, `price_override`. |
| `requester` | TEXT | Who raised it. |
| `subject` | TEXT | Short title. |
| `sku` | TEXT | Product, if relevant. |
| `size` | TEXT | Size, if relevant. |
| `qty` | INTEGER | Units requested. |
| `lease_id` | INTEGER FK → `leases.id` | Set on rent tickets. |
| `invoice_id` | INTEGER FK → `invoices.id` | Set when an invoice is tied to the ticket. |
| `status` | TEXT | `open` for all three at the start. |
| `notes` | TEXT | The request in plain words. |
| `created_at` | TEXT | ISO timestamp with timezone. |

**Why it matters:** This is the Boss's inbox. `type` and the populated foreign
keys tell the Boss which agent to route to; `status` is how a ticket is closed.

### `inventory`
| Field | Type | Notes |
|---|---|---|
| `sku` | TEXT | Part of the PK. |
| `name` | TEXT | Product name. |
| `size` | TEXT | `S`/`M`/`L`/`XL`, or `OS` (one size). Part of the PK. |
| `qty` | INTEGER | Units on hand. |
| `location` | TEXT | Aisle. |

**Why it matters:** The Inventory agent checks stock by SKU **and** size,
spots shortfalls (requested qty > on hand), and decides whether to restock.

### `pricing`
| Field | Type | Notes |
|---|---|---|
| `sku` | TEXT PK | Product. |
| `unit_cost` | REAL | What the shop pays. |
| `list_price` | REAL | What the shop charges. |

**Why it matters:** Accounting uses it to check margins before approving any
discount or purchase. Margin = `(list_price - unit_cost) / list_price`:
hoodie 62.1%, tee 71.4%, cap 72.7%, mug 75.0%.

### `vendors`
| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | Vendor id. |
| `name` | TEXT | Vendor name. |
| `specialty` | TEXT | What they supply. |
| `lead_days` | INTEGER | Days from order to delivery. |

Rows: 1 Bulldog Print Co (apparel reprint, 5 days), 2 Elm City Gifts (mugs and
small goods, 3 days), 3 QuickShip CT (local courier, 1 day).

**Why it matters:** Inventory picks the vendor whose `specialty` fits the SKU
and quotes the arrival date (`date_today + lead_days`). Rule: a vendor will not
ship while it has an unpaid invoice.

### `invoices`
| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | Invoice number. |
| `vendor_id` | INTEGER FK → `vendors.id` | Who is owed. |
| `amount` | REAL | Amount owed. |
| `due_date` | TEXT | Due date. |
| `status` | TEXT | `open` until paid. |
| `description` | TEXT | What it was for. |

**Why it matters:** Accounting watches it for overdue items
(`due_date < desk.date_today` and `status = 'open'`). An unpaid invoice blocks
that vendor from shipping, so it is the main link between Accounting and
Inventory.

### `payments`
| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | Payment id. |
| `kind` | TEXT | What was paid (invoice, rent, ...). |
| `ref_id` | INTEGER | The invoice or lease id paid. |
| `amount` | REAL | Amount. |
| `account` | TEXT | Which `cash_accounts.name` paid. |
| `paid_at` | TEXT | When. |
| `approved_by` | TEXT | The human who approved (required). |

**Why it matters:** The record of money that actually left. It is empty at the
start. A row is written only after a human approves, together with the
matching cash decrease and invoice status change. This is the audit trail.

### `leases`
| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | Lease id. |
| `space_name` | TEXT | Space (Chapel Street shop). |
| `landlord` | TEXT | Landlord (Elm City Properties). |
| `monthly_rent` | REAL | Rent per month ($2,400). |
| `next_due` | TEXT | Next due date (`2026-09-02`). |
| `notes` | TEXT | Free-form. |

**Why it matters:** The Facilities agent owns this table. It compares
`next_due` with `desk.date_today`, confirms the rent amount, and hands the
payment request to Accounting.

### `cash_accounts`
| Field | Type | Notes |
|---|---|---|
| `name` | TEXT PK | Account (`checking`). |
| `balance` | REAL | Current balance ($3,400). |
| `date` | TEXT | Balance date. |

**Why it matters:** Accounting checks it before preparing any payment. Rule:
the balance may never go negative, so a payment that would overdraw is refused.

### Action tables (created by the MCP server in the working database)

These four tables are not in the original database. `mcp_server/server.py`
creates them inside `data/campus_customs_new.db` the first time they are needed,
so `scripts/reset_db.py` clears them with everything else. Agents write them
only through MCP tools.

| Table | Written by | What a row is |
|---|---|---|
| `payment_requests` | `request_payment` (agent); `approve_payment` / `reject_payment` (human) | A prepared payment: kind (`invoice` or `rent`), ref id, amount, ticket, reason, status `pending_human_approval` / `approved` / `rejected`, and who decided. |
| `restock_requests` | `create_restock_request` (agent); released by `approve_payment` | A restock proposal (SKU, size, qty, vendor, expected arrival). Status `blocked_unpaid_invoice` until the vendor's last open invoice is paid, then `proposed`. Never an order. |
| `message_drafts` | `draft_customer_message` | A customer reply, status `draft`; never sent. |
| `price_proposals` | `propose_price_override` (agent); `approve_price_proposal` / `reject_price_proposal` (human) | A discounted unit price with its margin, awaiting a human. The `pricing` table is never changed. |

## How the three open tickets link across tables

| Ticket | Type | Links | What the agents must find |
|---|---|---|---|
| **101** Bulldog tee, S, qty 1 (Tauhid Zaman) | `customer_order` | `inventory` (CC-TEE-WHITE, S: **0** on hand) → `vendors` 1 Bulldog Print Co (apparel, 5 days) → `invoices` 501 ($840, due 2026-08-28, **open**, 3 days overdue) | Stock is short. The only apparel vendor will not ship until invoice 501 is paid, and paying it needs human approval and $840 of the $3,400 cash. Customer Service drafts the reply. |
| **102** Rent due (Elm City Properties) | `rent_notice` | `leases` 1 ($2,400, due 2026-09-02, 2 days away) → `cash_accounts` checking ($3,400) | Facilities confirms the rent is due. Accounting prepares a $2,400 payment for approval. Paying both rent and invoice 501 would need $3,240, leaving $160. |
| **103** Bulk hoodie discount (Yale AI Club) | `price_override` | `inventory` (CC-HOOD-NAVY, M: **8** on hand, 20 asked) → `pricing` (cost $22, list $58) → `vendors` 1 Bulldog Print Co (5 days, same unpaid invoice) | Inventory finds a 12-unit shortfall. Accounting checks the margin at any discounted price (62.1% at list). Customer Service drafts the reply. |

Shared constraint: tickets 101 and 103 both depend on Bulldog Print Co, and
tickets 101, 102 and the invoice all draw on the same $3,400 of cash.

## Agent team (`backend/`)

All five agents are PydanticAI agents on `gpt-6-luna` (set once in
`common/config.py`, override with `OPENAI_MODEL`) through Portkey, authenticated
with `PORTKEY_API_KEY`. Each has a prompt in `backend/prompts/<name>.md` and sees
only the MCP tools listed for it (`backend/mcp_client.py`). Shared types are in
`backend/models.py`.

| Agent | File | Role | MCP tools it can call |
|---|---|---|---|
| **Boss** | `boss.py` | Reads a ticket, routes it with `delegate`, checks the reports, sets the ticket status. Never looks up facts or changes the store itself. | `get_today`, `get_ticket`, `list_open_tickets`, `list_payment_requests`, `list_restock_requests`, `list_message_drafts`, `list_price_proposals`, `update_ticket` |
| **Inventory** | `inventory.py` | Stock by SKU and size, shortfalls, vendor choice, arrival date, restock proposals; hands vendor invoices to Accounting. | `get_today`, `get_ticket`, `list_open_tickets`, `check_stock`, `list_inventory`, `list_vendors`, `list_invoices`, `create_restock_request`, `list_restock_requests` |
| **Accounting** | `accounting.py` | Overdue invoices, cash, margins; prepares payment requests and price-override proposals for a human. | `get_today`, `get_ticket`, `list_open_tickets`, `get_pricing`, `check_discount`, `list_invoices`, `get_cash_balance`, `list_payments`, `list_payment_requests`, `request_payment`, `propose_price_override`, `get_lease` |
| **Facilities** | `facilities.py` | Lease and rent timing; hands the rent payment to Accounting. | `get_today`, `get_ticket`, `list_open_tickets`, `get_lease`, `get_cash_balance`, `list_payment_requests` |
| **Customer Service** | `customer_service.py` | Verifies the facts, then saves one customer reply as a draft. | `get_today`, `get_ticket`, `list_open_tickets`, `check_stock`, `get_pricing`, `list_vendors`, `list_restock_requests`, `list_payment_requests`, `list_message_drafts`, `draft_customer_message` |

**Delegation (`backend/delegation.py`).** The Boss has a `delegate(to, task,
reason)` tool. Each specialist has `hand_off(to, task, reason)` to pass work to a
colleague (for example Facilities to Accounting for rent, or Inventory to
Accounting for the vendor invoice). Both run the target agent one level deeper
and return its `SpecialistReport`. A handoff is refused when the depth limit (3)
is reached or when the target is already in the chain, so loops cannot happen.

**Audit trail (`backend/audit.py`, `backend/runner.py`).** Every agent loop runs
through `run_agent`, which appends one event per step to
`output/audit_trail.json`: `run_start`, `tool_call`, `tool_result`,
`delegation`, `handoff`, `agent_output`, `run_end` and `error`, each with
sequence number, UTC time, ticket id and agent. The file is a JSON array that is
re-read, extended and atomically replaced under a lock, so existing entries are
never wiped. Run the team with `python -m backend.run_tickets [ticket_id ...]`
after `python3 scripts/reset_db.py`.

## Backend routes (`backend/main.py`)

FastAPI server for the board. Start it from the `backend/` folder:

```bash
cd backend
uvicorn main:app --reload --port 8000
```

Facts and store updates still go through the MCP server; the API itself only
starts agent runs, reads the audit trail, and resets the database. Agents cannot
pay: the approve route is a human click that calls the human-only MCP tool in a
separate server process. CORS allows the front end on `localhost` / `127.0.0.1`.

- `GET /tickets`: the 3 tickets, each with `state` (`open` or `resolved`), its raw `status`, and `run_status` (`idle`, `running`, `finished`, `failed`).
- `POST /tickets/{ticket_id}/run`: starts the agent team on that ticket and returns `202` at once (`409` if it is already running, `404` if unknown).
- `GET /tickets/{ticket_id}/activity`: what the agents said and which tools they used (audit events, `?since=<seq>` for only new ones), the run status with `first_seq` (this run's first event) and outcome, and the records saved for the ticket (payment requests, restock requests, drafts, price proposals); poll it to refresh the board.
- `POST /payments/{request_id}/approve`: a human approves a prepared payment (body `{"approved_by": "Name"}`); it records the payment, lowers checking, and marks an invoice paid (`409` if refused, for example it would overdraw).
- `POST /payments/{request_id}/reject`: a human rejects a prepared payment (body `{"approved_by": "Name"}` is the decider).
- `POST /price-proposals/{proposal_id}/approve`: a human approves a discount proposal (body `{"approved_by": "Name"}`); no cash moves and `pricing` is unchanged.
- `POST /price-proposals/{proposal_id}/reject`: a human rejects a discount proposal (body `{"approved_by": "Name"}` is the decider).
- `GET /cash`: the current checking balance, what pending requests already claim, the payments made, and the pending payment requests and discount proposals (this is the Cash tab).
- `POST /reset`: puts `data/campus_customs_new.db` back to the original values for a fresh run (`409` while an agent run is in progress; the audit trail is kept).

Vendor purchases are paid through `approve` too: invoice payment requests
(such as invoice 501) are the money that leaves for a vendor. Paying a vendor's
last open invoice also releases its blocked restock proposals to `proposed`.
Restock requests themselves are internal proposals and are never ordered.

## MCP tools (`mcp_server/server.py`)

Every fact and every store update goes through these tools; there is no other
tool layer. Read tools open the database read-only. Write tools run in one
transaction. A missing row returns `found: false` or `ok: false`; nothing is
guessed. The four action tables (`payment_requests`, `restock_requests`,
`message_drafts`, `price_proposals`) are created by the server inside
`data/campus_customs_new.db`, so `scripts/reset_db.py` wipes them with the rest.

### Reads

| Tool | Reads | Used for |
|---|---|---|
| `get_today()` | `desk` | The shop's date. |
| `list_tickets()` | `tickets` | All tickets, open or resolved (used by the API). |
| `list_open_tickets()` | `tickets` | Every ticket not yet resolved. |
| `get_ticket(ticket_id)` | `tickets` | One ticket. |
| `check_stock(sku, size)` | `inventory` | Units on hand for one SKU and size (**101**). |
| `list_inventory(sku?)` | `inventory` | All sizes of a SKU. |
| `get_lease(lease_id)` | `leases`, `desk` | Rent, due date, days until due (**102**). |
| `get_pricing(sku)` | `pricing` | Cost, list price, margin (**103**). |
| `check_discount(sku, discounted_price)` | `pricing` | Margin at a proposed price. |
| `list_vendors()` | `vendors`, `invoices` | Specialty, lead days, and `can_ship` (false with an open invoice). |
| `list_invoices(status?, overdue_only?)` | `invoices`, `desk` | Invoices and days overdue. |
| `get_cash_balance(account)` | `cash_accounts`, `payment_requests` | Balance and what pending requests already claim. |
| `list_payments()` | `payments` | Money that has actually left. |
| `list_payment_requests(status?)` | `payment_requests` | Requests awaiting or past a human decision. |
| `list_restock_requests()` | `restock_requests` | Restock proposals. |
| `list_message_drafts(ticket_id?)` | `message_drafts` | Saved customer drafts. |
| `list_price_proposals(ticket_id?)` | `price_proposals` | Discount proposals awaiting a human (used by the API). |

### Store updates

| Tool | Writes | Rule it enforces |
|---|---|---|
| `create_restock_request(ticket_id, sku, size, qty, vendor_id)` | `restock_requests` (reads `inventory`, `vendors`, `invoices`) | A proposal only; the vendor is never contacted. Marked `blocked_unpaid_invoice` while the vendor has an open invoice. |
| `request_payment(kind, ref_id, amount, ticket_id, reason, requested_by)` | `payment_requests` (reads `invoices`, `leases`, `cash_accounts`) | No money moves. Amount must match the invoice or rent; refused if a duplicate exists or if it would overdraw checking once other pending requests are counted. |
| `draft_customer_message(ticket_id, recipient, subject, body)` | `message_drafts` (reads `tickets`) | Saved as `draft`, `sent: false`. There is no send tool. |
| `propose_price_override(ticket_id, sku, proposed_price, qty, rationale)` | `price_proposals` (reads `pricing`) | Needs a human; `pricing` is never changed; price must be above unit cost and not above list. |
| `update_ticket(ticket_id, status, note)` | `tickets` | Statuses `open`, `in_progress`, `waiting_approval`, `resolved`. Refuses `resolved` while a payment request or price proposal for the ticket awaits a human. |

### Human-only (given to no agent)

| Tool | Writes | Rule it enforces |
|---|---|---|
| `approve_payment(request_id, approved_by)` | `payments`, `cash_accounts`, `invoices`, `payment_requests` | One transaction: records the payment with the approver's name, lowers cash, marks an invoice `paid`, and releases that vendor's blocked restock proposals once nothing else is unpaid. Refused if it would overdraw. |
| `reject_payment(request_id, decided_by)` | `payment_requests` | Marks a pending request `rejected`. |
| `approve_price_proposal(proposal_id, approved_by)` | `price_proposals` | Marks a pending discount proposal `approved`; `pricing` is unchanged. |
| `reject_price_proposal(proposal_id, decided_by)` | `price_proposals` | Marks a pending discount proposal `rejected`. |

All four refuse to run unless the server was launched by
`scripts/approve_payment.py` (which sets `CC_HUMAN_APPROVER`). The agents'
server process never has that setting, and the tools are not in any agent's
allowlist.

### Which tools unlock which ticket

| Ticket | First lookups | Then |
|---|---|---|
| **101** tee, S | `check_stock` (0 on hand) | `list_vendors` shows Bulldog Print Co cannot ship; `create_restock_request` is blocked by invoice 501; `request_payment` for $840; `draft_customer_message`. |
| **102** rent | `get_lease` (2 days away) | `get_cash_balance`; `request_payment` for $2,400. Both requests together total $3,240 of $3,400, so a human must see the $160 left. |
| **103** hoodies | `get_pricing` (62.1%), `check_stock` (8 of 20) | `check_discount`; `propose_price_override`; `create_restock_request` (also blocked by 501); `draft_customer_message`. |

## Dashboard architecture (`frontend/`)

React + Vite + TypeScript, started with `npm run dev` from `frontend/` on
`http://localhost:5173`. It talks only to the backend routes above (base URL
`VITE_API_URL`, default `http://localhost:8000`); the backend allows exactly the
Vite origin through CORS. The visual theme is described in `output/design.md`.

- **Data flow.** The board polls `GET /tickets` and `GET /cash` every few seconds
  (faster during a run) and `GET /tickets/{id}/activity?since=<seq>` about once a
  second while a quest runs. Events are merged by sequence number so overlapping
  polls cannot duplicate lines.
- **State from the audit trail.** The party view, dialogue log and end-of-quest
  summary are all derived from the audit events of the latest quest
  (`frontend/src/party.ts`): who is acting comes from the `run_start`/`run_end`
  stack, spells from `tool_call`, speech from `delegation`/`handoff`, and summary
  cards from each agent's last `agent_output`. A later Boss follow-up pass is
  folded into the same quest.
- **Components.** `QuestBoard` (tickets as scrolls), `Party` (Boss + 4 NPC cards),
  `DialogueLog`, `QuestSummary`, `GoldVault` (live checking balance), and
  `SealModal` (the human approval step for payments and discount proposals).
- **Human step.** Only the Seal modal calls the approve/reject routes, and it
  needs the person's name first. Agents have no path to those routes or tools.

## Resolved run (Problem 9)

Clean run from `scripts/reset_db.py` (checking started at **$3,400.00**). The
team ran on 101, 102 and 103; a human (Blessy Bellamy) then stamped the two
payments and the discount; the Boss's follow-up pass (`finalize_ticket` in
`backend/boss.py`) set each ticket to `resolved`.

| Ticket | Final status | Cash change | Human approval |
|---|---|---|---|
| 101 | resolved | −$840.00 (vendor invoice 501) | payment request 1 |
| 102 | resolved | −$2,400.00 (Chapel Street rent) | payment request 2 |
| 103 | resolved | $0.00 | price proposal 1 ($52.20 per hoodie) |

Ending checking balance: **$160.00** ($3,400.00 − $840.00 − $2,400.00), equal to
`cash_accounts` in `data/campus_customs_new.db`. Details: `output/resolved_tickets.json`,
`output/desk_tickets.html` (Actual and Cash tabs), `output/resolved_board.html`,
and the full trace in `output/audit_trail.json`. `scripts/build_outputs.py`
regenerates those files from the database and the audit trail. The audit trail
is append-only, so it also holds an earlier discarded attempt and a correction
note, both marked as system events.

## Configuration notes (deviations from `AGENTS.md`)

- **Model.** `AGENTS.md` names `gpt-5.6-luna` as the default. This project's assignments
  require `gpt-6-luna`, so that is the default in `common/config.py`; it stays
  configurable through `OPENAI_MODEL` and is not hard-coded anywhere else.
- **Dependencies.** `AGENTS.md` asks for `pydantic-ai-slim[openai]`. `requirements.txt`
  uses `pydantic-ai-slim[openai,mcp]` because the agents reach the database through
  the MCP server and need the `mcp` extra. The full `pydantic-ai` package is not used.
- **Ports.** The backend is documented on port 8000 and the front end on 5173 as
  assigned. If another program holds either port on your machine, stop it first;
  the backend's CORS allows only the 5173 origin (plus `EXTRA_FRONTEND_ORIGINS`).

## Safety

- **Token and request limits.** Each ticket runs under one shared budget
  (`UsageLimits` in `backend/runner.py`): 40 model requests and 80,000 tokens by
  default, counted across the Boss and every specialist it calls. Change them
  with `MAX_REQUESTS_PER_TICKET` and `MAX_TOKENS_PER_TICKET`. Going over stops
  the run with an `error` event in the audit trail. Delegation depth is capped at
  3, and an agent cannot be called twice in one chain.
- **Human approval for payments.** Agents can only call `request_payment`, which
  writes a pending request and moves no money. Only a person running
  `python scripts/approve_payment.py approve <id> --by "Name"` can execute it,
  and the name is stored in `payments.approved_by`. Payments that would make a
  balance negative are refused both when requested and when approved. The Boss
  cannot mark a ticket `resolved` while approvals are pending.
- **No automated customer messages.** The only customer tool is
  `draft_customer_message`, which saves a draft on the board. No agent has a
  send, email or SMS tool, and the Customer Service prompt says "draft saved",
  never "sent".
- **No external vendor calls.** Restocks are internal proposals in
  `restock_requests`. No agent or tool contacts a vendor, landlord or customer,
  and vendors with unpaid invoices are marked blocked.
- **Follow-up passes cannot bypass approval.** The Boss may only set a ticket
  `resolved` after the humans have decided, and the server refuses `resolved`
  while any payment request or price proposal for the ticket is still pending.
- **Data boundaries.** All facts come from the MCP server on
  `data/campus_customs_new.db`; the original database is refused in
  `common/config.py`. Each agent only sees its own tools, and `output/audit_trail.json`
  records every call so a person can review what happened.

## Rules the tools enforce

- Today is `desk.date_today`.
- Every payment needs human approval and records the approver.
- A payment that would make a balance negative is refused.
- Vendors do not ship while they have an unpaid invoice.
- All customer messages are drafts kept on the board; nothing is sent.
- All agents use `gpt-6-luna` via Portkey (`PORTKEY_API_KEY`).
