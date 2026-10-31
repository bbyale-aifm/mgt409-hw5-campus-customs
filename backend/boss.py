"""The Boss agent: reads open tickets, routes them to specialists, closes them out."""
from functools import lru_cache

from pydantic_ai.usage import RunUsage

from .agent_base import build_agent
from .delegation import add_boss_tools
from .models import Deps, TicketOutcome
from .runner import run_agent


@lru_cache
def get_agent():
    agent = build_agent("boss", TicketOutcome)
    add_boss_tools(agent)
    return agent


async def handle_ticket(ticket_id: int, usage: RunUsage | None = None) -> TicketOutcome:
    """Run the whole team on one ticket under one shared token budget."""
    deps = Deps(ticket_id=ticket_id, agent="boss", trail=["boss"])
    prompt = f"Handle ticket {ticket_id}. Read it, delegate, then report the outcome."
    return await run_agent("boss", prompt, deps, usage or RunUsage())


async def finalize_ticket(ticket_id: int, usage: RunUsage | None = None) -> TicketOutcome:
    """After humans have decided on pending items, let the Boss close the ticket out."""
    deps = Deps(ticket_id=ticket_id, agent="boss", trail=["boss"])
    prompt = (
        f"Follow-up on ticket {ticket_id}: humans have now decided on the payments and price proposals "
        "that were waiting. Do NOT delegate again. Check list_payment_requests and list_price_proposals for "
        "this ticket. If nothing is still pending, call update_ticket with status resolved and a one-sentence "
        "note that says what the humans decided; otherwise keep waiting_approval. Then report the outcome."
    )
    return await run_agent("boss", prompt, deps, usage or RunUsage())
