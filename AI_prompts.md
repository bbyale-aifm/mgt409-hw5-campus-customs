# AI Prompts Log — Homework 5: Campus Customs Operations Command Center

Prompt log for the project. One section per problem: the problem, the first
prompt (in my own words for Setup and Problems 2 to 4, verbatim from Problem 5 on), and any follow-up prompt with one sentence on what
the first run missed.

## Setup (before Problem 1)

**Prompt:** Copy the original database to `data/campus_customs_new.db`, point
the MCP server and backend at the copy only, and give me one command that
resets the copy to the original values before every full ticket run. Use
`desk.date_today` as today, require human approval for every payment, refuse
payments that would overdraw cash, block vendors from shipping while they have
unpaid invoices, keep all messages as local drafts, and run every agent on
`gpt-6-luna` through Portkey.

**Follow-up:** none yet.

## Problem 2: Study the Campus Customs Database

**Prompt:** Look inside `data/campus_customs.db` and make sure
`data/campus_customs_new.db` exists as the working copy. Go through every
table (desk, tickets, inventory, pricing, vendors, leases, cash_accounts,
payments, invoices) and work out how the three open tickets connect to them.
Then write `output/harness.md` listing each table with its fields and a short
note on why it matters to the agent team (Inventory uses `inventory`,
Accounting uses `invoices` and `payments`, Facilities uses `leases`).

**Follow-up:** none yet.

## Problem 3: Build the MCP Server

**Prompt:** Build a FastMCP server in `mcp_server/` that reads only from
`data/campus_customs_new.db`. Give it three simple, clearly named read tools,
one for each open ticket (101, 102, 103), returning real database data and
nothing invented. Then update `output/harness.md` to list the three tools,
with the table each one reads, the ticket it unlocks, and one sentence on why
it is the right tool. Add `mcp_server/README.md` explaining the server's
purpose, the database it uses and the three tools.

**Follow-up:** none yet.

## Problem 4: Add the MCP server to vibe coder and test each tool

**Prompt:** Connect Claude Code to the FastMCP server by writing a `.mcp.json`
at the project root that launches `mcp_server/` against
`data/campus_customs_new.db`. Then type one real prompt per tool in Claude
Code, let it call `check_stock`, `get_lease` and `get_pricing`, and save the
evidence in `output/mcp_smoke.json` as an array of entries, each with the
`prompt`, the exact `tool_name` and the exact `tool_output` from the database.

**Follow-up:** Run the same three prompts inside a Claude Code session opened in the project folder, so it uses `.mcp.json` and the real MCP tools, and copy each tool's exact output into `output/mcp_smoke.json`. The first attempt (a script launching a headless Claude Code) failed because that copy was not signed in, so the calls had to come from a normal session.

## Problem 5: Build the Agent Team and Grow The MCP Tools

**Prompt (verbatim):**

````text
Problem 5: Build the Agent Team and Grow The MCP Tools

1. Agent Files & Structure:

* Build five PydanticAI agents in `backend/`: `boss.py`, `inventory.py`, `accounting.py`, `facilities.py`, and `customer_service.py`.

* Create detailed, role-specific prompt files in `backend/prompts/` (`boss.md`, `inventory.md`, `accounting.md`, `facilities.md`,`customer_service.md`) reflecting all shop rules and delegate responsibilities.

* Put shared data types and models in `backend/models.py`.

* Configure all agents to use `gpt-6-luna` through Portkey using `PORTKEY_API_KEY`.

* Enable agent-to-agent delegation so the Boss can route tickets and specialists can hand off tasks cleanly.

2. MCP Server Expansion (`mcp_server/`):

* Add any new execution tools needed to resolve open tickets directly to the FastMCP server in `mcp_server/` querying `data/campus_customs_new.db`.

* Ensure all agent facts and store updates pass through the MCP server (do not create a secondary tools layer).

3. Audit Trail (`output/audit_trail.json`):

* Wire every agent loop to append execution steps and handoffs to `output/audit_trail.json`. Ensure the file appends data rather than wiping existing logs.

4. Documentation Updates (`output/harness.md` & `mcp_server/README.md`):

* Update `output/harness.md` to list each agent role, every MCP tool, and the database table each tool reads/writes.

* Add a Safety section in `output/harness.md` documenting guardrails (token usage limits, human approval for financial payments, preventing automated customer messaging or external vendor calls).

* Update `mcp_server/README.md` with the complete, updated list of MCP tools.

5. Update `AI_prompts.md`:

* Log this prompt under "Problem 5: Build the Agent Team and Grow The MCP Tools".
````

**Follow-up:** none yet.

## Problem 6: Plan The Three Tickets

**Prompt (verbatim):**

````text
Problem 6: Plan The Three Tickets

1. Build `output/desk_tickets.html`:

* Create a standalone, tabbed HTML file at `output/desk_tickets.html` that can be opened directly in a browser.

* Include 5 tabs total: Ticket 101, Ticket 102, Ticket 103, Cash, and Reflection.

* Place a short "coming later" placeholder note in both the Cash and Reflection tabs.

2. Populate Ticket Tabs (Expected vs. Actual Structure):

* Each ticket tab must contain an Expected section and leave a blank/placeholder Actual section for future agent runs.

* Fill out the Expected section for each ticket using the following targeted delegation plans:
   * Ticket 101 (`customer_order` — Tauhid Zaman, Bulldog tee, size S, qty 1):
      * Who Boss calls FIRST & why: Inventory — to check stock levels, locate vendor lead times, and determine how to restock the missing Bulldog tee.

      * Agent Delegations: Boss hands off to Inventory to check stock and vendor details. If the vendor is blocked by an unpaid invoice, Inventory delegates to Accounting to resolve it. Accounting then hands off to Customer Service to pass along the status and draft the customer update.

      * Expected MCP Tools: `get_inventory_by_sku`, `get_vendor_details`, `get_unpaid_invoices`, `prepare_payment_draft`
   * Ticket 102 (`rent_notice` — Elm City Properties, $2,400 rent due 2026-09-02):
      * Who Boss calls FIRST & why: Facilities — to inspect lease terms, verify due dates, and confirm the exact rent amount owed to Elm City Properties.

      * Agent Delegations: Boss hands off to Facilities to confirm lease agreement terms and rent due dates. Facilities delegates to Accounting to verify available cash balances and prepare the payment request for human approval.

      * Expected MCP Tools: `get_lease_details`, `get_cash_balance`, `prepare_payment_draft`
   * Ticket 103 (`price_override` — Yale AI Club, bulk hoodie discount):
      * Who Boss calls FIRST & why: Inventory — to verify current stock levels (confirming only 8 are available) and check restock options for the remaining 12.

      * Agent Delegations: Boss hands off to Inventory to verify stock count and vendor availability for the 20-hoodie request. Inventory delegates to Accounting to run a margin check on the requested discount. Accounting hands off to Customer Service to pass the approved pricing proposal and draft the final reply.

      * Expected MCP Tools: `get_inventory_by_sku`, `check_item_margin`, `get_pricing_rules`

3. Update `AI_prompts.md`:

* Log this exact prompt under a new section titled "Problem 6: Plan The Three Tickets".

***
````

**Follow-up:** Replace the expected tool names with the ones that exist on the
real MCP server. The first version used guessed names (`get_inventory_by_sku`,
`get_vendor_details`, `get_unpaid_invoices`, `prepare_payment_draft`,
`get_lease_details`, `check_item_margin`, `get_pricing_rules`), which the server
does not have; they map to `check_stock`, `list_vendors`, `list_invoices`,
`request_payment`, `get_lease`, `check_discount` and `get_pricing`.

## Problem 7: Backend routes

**Prompt (verbatim):**

````text
Problem 7: Backend routes
Next, our task is to create the backend that powers the front-end that we will create in Problem 8. Use FastAPI in backend/main.py and add routes to:

* Return the 3 tickets, whether each ticket is open or resolved
* take ticket id and run agent team on ticket
* Document what agents say and the tools they used, so that the board can refresh
* Approve a payment or purchase after a human clicks approve. agents cannot pay, they only prepare the payment. This route changes the cash tab.
* return the current checking balance from cash accounts
* reset database to the original values when you want to try a fresh run

From the back end folder, the server should start with:
uvicorn main:app --reload --port 8000
This will turn on the backend so that the frontend can find the routes there. Include each route in one line (the URL and what it does) and document in output/harness.md
````

**Follow-up:** none yet.

## Problem 8: Agent Dashboard

**Prompt (verbatim):**

````text
Problem 8: agent dashboard 

1. Front-End Setup (`frontend/`):

* Build a React + Vite + TypeScript application in `frontend/` configured to call the FastAPI backend at `http://localhost:8000`.

* Add CORS middleware in `backend/main.py` allowing requests from the Vite origin (`http://localhost:5173`).

* Ensure the app launches from `frontend/` using `npm run dev`.

2. RPG Quest UI & Features:

* Quest Board (Ticket List): Render the 3 tickets as active RPG quest scrolls showing status badges (open vs. completed).

* Boss & NPC Party Execution: Allow selecting a quest where the Boss acts as the Main Player leading an NPC party (Inventory = Merchant NPC, Accounting = Treasury Mage NPC, Facilities = Castle Steward NPC, Customer Service = Town Herald NPC).

* Live Party Dialogue Log: Stream dialogue and tool actions in real time, displaying distinct character cards and glowing action indicators as NPCs carry out tasks.

* Quest Victory & Summaries: Automatically mark quests as completed upon run completion and display an end-of-quest summary card for each NPC's actions.

* Gold Vault & Guild Master Approval: Display the live checking account balance as the "Shop Gold Vault." Include an explicit human "Guild Master Seal" approval modal for pending payments/purchases, updating the gold vault balance immediately upon approval.

3. Documentation (`output/design.md`):

* Write `output/design.md` describing the RPG quest dashboard theme. Detail the character class assignments (Boss as Main Player, specialists as NPCs), quest log mechanics, gold vault display, and creative UX choices that make human oversight feel like playing an RPG.

4. Update `AI_prompts.md`:

* Log this prompt under a new section titled "Problem 8: Agent Dashboard"
````

**Follow-up:** none yet.

## Problem 9: Resolve the Tickets

**Prompt (verbatim):**

````text
Problem 9: Resolve the Tickets

1. Database Reset & Clean Execution:

* Reset `data/campus_customs_new.db` using original values from `data/campus_customs.db` and log the starting checking balance.

* Process and resolve all three tickets (101, 102, and 103) through the agent team loop.

2. Update `output/desk_tickets.html`:

* On each ticket tab (101, 102, 103), fill in the Actual section documenting which agents worked, what delegations occurred, and the tools used. Keep the Expected section intact for comparison.

* On the Cash tab, itemize the finances: starting checking balance after reset, itemized cash changes for each ticket resolution (specifying the payout/purchase description and exact dollar amount), and ending checking balance matching `cash_accounts` in `data/campus_customs_new.db`. Verify math accuracy.

3. Deliverables & Outputs:

* Create `output/resolved_tickets.json`: Include ticket ID, final status, concise outcome summary, agent contributions, and any human approvals for each ticket.

* Create `output/resolved_board.html`: A double-clickable HTML page containing dashboard screenshots/renders of each resolved ticket (101, 102, 103).

* Append execution traces for the live runs to `output/audit_trail.json`.

* Finalize `output/harness.md`: Ensure complete coverage of database tables, MCP tools, the 5 agents, backend API routes, dashboard architecture, and safety guardrails.

4. Update `AI_prompts.md`:

* Log this prompt under a new section titled "Problem 9: Resolve the Tickets".
````

**Follow-up:** The first full run left ticket 103 with no discount proposal because
the Accounting prompt only said to suggest a price when asked. I made a proposal
mandatory on price-override tickets, reset the database, and re-ran all three
tickets; the first attempt stays in the audit trail marked as discarded. Resolving
103 also needed a human approval for discount proposals, so I added
`approve_price_proposal` / `reject_price_proposal` as human-only MCP tools with
routes and a Seal-modal section, and made paying an invoice release the vendor's
blocked restock proposals.
