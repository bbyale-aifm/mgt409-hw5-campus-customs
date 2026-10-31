"""Shared data types for the Campus Customs agent team."""
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
SPECIALISTS: tuple[str, ...] = ("inventory", "accounting", "facilities", "customer_service")


class SpecialistReport(BaseModel):
    """What a specialist returns to whoever delegated to it."""

    agent: AgentName
    ticket_id: int
    findings: list[str] = Field(description="Facts read from MCP tools, each with the number it came from.")
    actions_taken: list[str] = Field(description="MCP write tools called and their results.")
    needs_human_approval: list[str] = Field(
        default_factory=list, description="Payments or price changes waiting for a human."
    )
    handoffs_made: list[str] = Field(default_factory=list, description="Colleagues asked for help, and why.")
    recommendation: str


class TicketOutcome(BaseModel):
    """The Boss's final word on one ticket."""

    ticket_id: int
    status: Literal["in_progress", "waiting_approval", "resolved"]
    summary: str = Field(description="Two or three plain sentences for the shop owner.")
    delegations: list[str] = Field(description="Which specialist did what.")
    pending_human_approvals: list[str] = Field(default_factory=list)
    drafts_saved: list[str] = Field(default_factory=list)


@dataclass
class Deps:
    """Run-time context handed to every agent run and tool."""

    ticket_id: int
    agent: str = "boss"
    depth: int = 0  # how many delegations/handoffs deep this run is
    max_depth: int = 3
    trail: list[str] = field(default_factory=list)  # chain of agents that led here
