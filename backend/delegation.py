"""Agent-to-agent delegation: the Boss routes tickets, specialists hand off to each other.

Every delegation and handoff runs the target agent with the same usage budget,
one level deeper, and is written to the audit trail before it starts.
"""
from typing import Literal

from pydantic_ai import Agent, RunContext

from .audit import log_event
from .models import Deps, SpecialistReport
from .runner import run_agent

Specialist = Literal["inventory", "accounting", "facilities", "customer_service"]


async def _call(ctx: RunContext[Deps], to: str, task: str, reason: str, kind: str) -> SpecialistReport | str:
    d = ctx.deps
    if d.depth >= d.max_depth:
        return f"Refused: handoff depth limit ({d.max_depth}) reached. Put this in your recommendation instead."
    if to == d.agent or to in d.trail:
        return f"Refused: {to} is already in this chain ({' > '.join(d.trail)}). Use its earlier report."
    log_event(d.agent, kind, d.ticket_id, to=to, task=task, reason=reason, chain=d.trail)
    child = Deps(ticket_id=d.ticket_id, agent=to, depth=d.depth + 1, max_depth=d.max_depth, trail=[*d.trail, to])
    prompt = f"Ticket {d.ticket_id}. From {d.agent}: {task}\nWhy: {reason}"
    return await run_agent(to, prompt, child, ctx.usage)


def add_boss_tools(agent: Agent) -> None:
    @agent.tool
    async def delegate(ctx: RunContext[Deps], to: Specialist, task: str, reason: str) -> SpecialistReport | str:
        """Route work to a specialist and get their report back.

        to: inventory (stock, vendors, restocks), accounting (invoices, cash,
        payment requests, margins), facilities (leases, rent), customer_service
        (customer-facing drafts). task: exactly what to do, with ids.
        """
        return await _call(ctx, to, task, reason, "delegation")


def add_specialist_tools(agent: Agent, me: str) -> None:
    @agent.tool
    async def hand_off(ctx: RunContext[Deps], to: Specialist, task: str, reason: str) -> SpecialistReport | str:
        """Hand part of the work to a colleague (never yourself) and get their report.

        Use it when the next step belongs to another role, e.g. facilities
        hands a rent payment request to accounting. task must carry every id
        and amount the colleague needs.
        """
        return await _call(ctx, to, task, reason, "handoff")
