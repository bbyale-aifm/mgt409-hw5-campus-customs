"""FastAPI backend for the Campus Customs board.

Start (from this folder):  uvicorn main:app --reload --port 8000

Every fact and store update goes through the MCP server. The only things this
file does itself are start agent runs, read the audit trail, and reset the
working database. Agents cannot pay: approving a payment is a human click that
calls the human-only MCP tool through a separate server process.
"""
import asyncio
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # so `backend.*` and `common.*` import

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastmcp import Client  # noqa: E402
from fastmcp.client.transports import StdioTransport  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402
from pydantic_ai.usage import RunUsage  # noqa: E402

from backend.audit import log_event, read_events  # noqa: E402
from backend.boss import handle_ticket  # noqa: E402
from common.config import DB_PATH, ROOT  # noqa: E402
from scripts.reset_db import reset as reset_database  # noqa: E402

RUNS: dict[int, dict] = {}  # ticket_id -> {"status": running|finished|failed, ...}


def _transport(human: bool = False) -> StdioTransport:
    env = {"CAMPUS_CUSTOMS_DB": str(DB_PATH.relative_to(ROOT))}
    if human:
        env["CC_HUMAN_APPROVER"] = "1"  # only this process may run approve/reject
    return StdioTransport(sys.executable, ["-m", "mcp_server.server"], cwd=str(ROOT), env=env)


_client: Client | None = None
_client_lock = asyncio.Lock()


async def _shared_client() -> Client:
    """One long-lived MCP server process for routine calls, so each request does not start a new one."""
    global _client
    async with _client_lock:
        if _client is None or not _client.is_connected():
            _client = Client(_transport())
            await _client.__aenter__()
        return _client


async def mcp_call(tool: str, args: dict | None = None, human: bool = False):
    """Call one MCP tool. Human-only tools get their own short-lived server process."""
    if human:
        async with Client(_transport(human=True)) as client:
            return (await client.call_tool(tool, args or {})).data
    client = await _shared_client()
    return (await client.call_tool(tool, args or {})).data


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    for t in RUNS.values():
        if t.get("task"):
            t["task"].cancel()
    if _client is not None:
        await _client.__aexit__(None, None, None)


app = FastAPI(title="Campus Customs backend", lifespan=lifespan)
FRONTEND_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]  # the Vite dev server
FRONTEND_ORIGINS += [o for o in os.environ.get("EXTRA_FRONTEND_ORIGINS", "").split(",") if o]
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Approval(BaseModel):
    approved_by: str = Field(min_length=1, description="The human's name, stored with the payment.")


def _ticket_state(t: dict) -> dict:
    run = RUNS.get(t["id"], {})
    return {
        **t,
        "state": "resolved" if t["status"] == "resolved" else "open",
        "run_status": run.get("status", "idle"),
    }


async def _get_ticket_or_404(ticket_id: int) -> dict:
    t = await mcp_call("get_ticket", {"ticket_id": ticket_id})
    if not t.get("found"):
        raise HTTPException(404, f"ticket {ticket_id} not found")
    return t


async def _run_team(ticket_id: int) -> None:
    run = RUNS[ticket_id]
    usage = RunUsage()
    try:
        outcome = await handle_ticket(ticket_id, usage)
        run.update(status="finished", outcome=outcome.model_dump())
    except Exception as exc:  # the runner already logged an `error` event
        run.update(status="failed", error=f"{type(exc).__name__}: {exc}")
    run.update(tokens=usage.total_tokens, requests=usage.requests)


# GET /tickets: the 3 tickets, each marked open or resolved (plus its last run status).
@app.get("/tickets")
async def list_tickets():
    return [_ticket_state(t) for t in await mcp_call("list_tickets")]


# POST /tickets/{ticket_id}/run: start the agent team on a ticket (returns at once; poll the activity route).
@app.post("/tickets/{ticket_id}/run", status_code=202)
async def run_ticket(ticket_id: int):
    await _get_ticket_or_404(ticket_id)
    if RUNS.get(ticket_id, {}).get("status") == "running":
        raise HTTPException(409, f"ticket {ticket_id} is already running")
    seen = read_events()
    RUNS[ticket_id] = {"status": "running", "first_seq": (seen[-1]["seq"] if seen else 0) + 1}  # this run's events start here
    RUNS[ticket_id]["task"] = asyncio.create_task(_run_team(ticket_id))
    return {"ticket_id": ticket_id, "run_status": "running"}


# GET /tickets/{ticket_id}/activity: what the agents said and which tools they used (audit events, ?since=<seq> for new ones only), plus the records they saved.
@app.get("/tickets/{ticket_id}/activity")
async def ticket_activity(ticket_id: int, since: int = 0):
    ticket = await _get_ticket_or_404(ticket_id)
    run = {k: v for k, v in RUNS.get(ticket_id, {"status": "idle"}).items() if k != "task"}
    records = {
        "payment_requests": [r for r in await mcp_call("list_payment_requests") if r["ticket_id"] == ticket_id],
        "restock_requests": [r for r in await mcp_call("list_restock_requests") if r["ticket_id"] == ticket_id],
        "message_drafts": await mcp_call("list_message_drafts", {"ticket_id": ticket_id}),
        "price_proposals": await mcp_call("list_price_proposals", {"ticket_id": ticket_id}),
    }
    return {"ticket": _ticket_state(ticket), "run": run, "events": read_events(ticket_id, since), "records": records}


# POST /payments/{request_id}/approve: a human approves a prepared payment (body: approved_by); pays it and lowers checking.
@app.post("/payments/{request_id}/approve")
async def approve_payment(request_id: int, body: Approval):
    result = await mcp_call("approve_payment", {"request_id": request_id, "approved_by": body.approved_by}, human=True)
    if not result.get("ok"):
        raise HTTPException(409, result.get("error", "approval failed"))
    log_event("human", "payment_approved", None, request_id=request_id, approved_by=body.approved_by, **result)
    return result


# POST /payments/{request_id}/reject: a human rejects a prepared payment (body: approved_by is the decider's name).
@app.post("/payments/{request_id}/reject")
async def reject_payment(request_id: int, body: Approval):
    result = await mcp_call("reject_payment", {"request_id": request_id, "decided_by": body.approved_by}, human=True)
    if not result.get("ok"):
        raise HTTPException(409, result.get("error", "rejection failed"))
    log_event("human", "payment_rejected", None, request_id=request_id, decided_by=body.approved_by)
    return result


# POST /price-proposals/{proposal_id}/approve: a human approves a discount proposal (body: approved_by); the pricing table is not changed.
@app.post("/price-proposals/{proposal_id}/approve")
async def approve_price(proposal_id: int, body: Approval):
    result = await mcp_call("approve_price_proposal", {"proposal_id": proposal_id, "approved_by": body.approved_by}, human=True)
    if not result.get("ok"):
        raise HTTPException(409, result.get("error", "approval failed"))
    log_event("human", "price_proposal_approved", None, proposal_id=proposal_id, approved_by=body.approved_by)
    return result


# POST /price-proposals/{proposal_id}/reject: a human rejects a discount proposal (body: approved_by is the decider's name).
@app.post("/price-proposals/{proposal_id}/reject")
async def reject_price(proposal_id: int, body: Approval):
    result = await mcp_call("reject_price_proposal", {"proposal_id": proposal_id, "decided_by": body.approved_by}, human=True)
    if not result.get("ok"):
        raise HTTPException(409, result.get("error", "rejection failed"))
    log_event("human", "price_proposal_rejected", None, proposal_id=proposal_id, decided_by=body.approved_by)
    return result


# GET /cash: current checking balance, what pending requests already claim, and the payments made so far.
@app.get("/cash")
async def cash():
    balance = await mcp_call("get_cash_balance", {"account": "checking"})
    return {
        **balance,
        "payments": await mcp_call("list_payments"),
        "pending_requests": await mcp_call("list_payment_requests", {"status": "pending_human_approval"}),
        "pending_price_proposals": [
            p for p in await mcp_call("list_price_proposals") if p["status"] == "pending_human_approval"
        ],
    }


# POST /reset: put the working database back to the original values for a fresh run (the audit trail is kept).
@app.post("/reset")
async def reset():
    if any(r.get("status") == "running" for r in RUNS.values()):
        raise HTTPException(409, "an agent run is in progress; wait for it to finish")
    reset_database()
    RUNS.clear()
    log_event("system", "database_reset", None, database=DB_PATH.name)
    return {"ok": True, "database": DB_PATH.name, "balance": (await mcp_call("get_cash_balance"))["balance"]}
