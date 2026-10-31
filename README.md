# Homework 5: Campus Customs Command Center

A team of five PydanticAI agents (Boss, Inventory, Accounting, Facilities, Customer Service) that resolve Campus Customs desk tickets through a FastMCP server, with a FastAPI backend and a React quest dashboard. Every payment needs a human approval. Customer messages are drafts only.

## Layout

| Path | What it holds |
|---|---|
| `data/campus_customs.db` | Original database. Never written to. |
| `data/campus_customs_new.db` | Working copy the MCP server and agents use. |
| `mcp_server/` | FastMCP server (`server.py`) and its README. |
| `backend/` | FastAPI app (`main.py`), models, agents, and `prompts/` (five agent prompts). |
| `frontend/` | React + Vite + TypeScript dashboard. |
| `scripts/` | Reset, smoke test, human approval CLI, output builder. |
| `output/` | `harness.md`, `design.md`, `desk_tickets.html`, `mcp_smoke.json`, `resolved_tickets.json`, `resolved_board.html`, `audit_trail.json`. |
| `AI_prompts.md` | The prompts used for each problem. |

## Setup

Run all commands from this folder (`Homework 5/`) unless noted.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env        # then set PORTKEY_API_KEY in .env
cd frontend && npm install && cd ..
```

`.env` is git-ignored. `OPENAI_MODEL` in `.env` sets the model for every agent.

## 1. Clean database copy (reset before a full run)

The working copy is made from the original. This also clears all agent actions (payment requests, restock requests, drafts, price proposals):

```bash
.venv/bin/python scripts/reset_db.py
```

It should print `today=2026-08-31, checking=$3,400.00`.

The same thing by hand, with the MCP server and backend stopped (the original is only ever read):

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

## 2. Start the MCP server

`.mcp.json` registers it for Claude Code. To run it directly:

```bash
.venv/bin/python -m mcp_server.server
```

Smoke test through the tools: `.venv/bin/python scripts/mcp_smoke.py`.

## 3. Start the FastAPI backend

```bash
cd backend
../.venv/bin/uvicorn main:app --reload --port 8000
```

## 4. Start the React board

In a second terminal:

```bash
cd frontend
npm run dev
```

Open http://localhost:5173. The dashboard reads the API at `VITE_API_URL` (default `http://localhost:8000`, see `frontend/.env.example`).

## 5. Run all three tickets

Reset the database first so the run starts from the original data:

```bash
.venv/bin/python scripts/reset_db.py
```

Then either click Run on each ticket in the board or use the CLI:

```bash
.venv/bin/python -m backend.run_tickets
```

Payments and discounts wait for a human. Approve them in the board's seal dialog, or:

```bash
.venv/bin/python scripts/approve_payment.py list
.venv/bin/python scripts/approve_payment.py approve <id> --by "Your Name"
```

Every agent action is appended to `output/audit_trail.json`. See `output/harness.md` for the full design.
