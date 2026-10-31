"""Runs one agent loop and writes every step to output/audit_trail.json."""
import importlib
import os

from pydantic_ai import Agent
from pydantic_ai.messages import TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.usage import RunUsage, UsageLimits

from .audit import log_event
from .models import Deps

# Token and request ceilings for one ticket, shared by the Boss and every specialist it calls.
LIMITS = UsageLimits(
    request_limit=int(os.environ.get("MAX_REQUESTS_PER_TICKET", 40)),
    total_tokens_limit=int(os.environ.get("MAX_TOKENS_PER_TICKET", 80_000)),
)

_AGENT_MODULES = {
    "boss": "backend.boss",
    "inventory": "backend.inventory",
    "accounting": "backend.accounting",
    "facilities": "backend.facilities",
    "customer_service": "backend.customer_service",
}


def get_agent(name: str) -> Agent:
    return importlib.import_module(_AGENT_MODULES[name]).get_agent()


async def run_agent(name: str, prompt: str, deps: Deps, usage: RunUsage, agent: Agent | None = None):
    """Run one agent to its final output, logging each step. Returns the output."""
    agent = agent or get_agent(name)
    log_event(name, "run_start", deps.ticket_id, prompt=prompt, depth=deps.depth, chain=deps.trail)
    try:
        async with agent.iter(prompt, deps=deps, usage=usage, usage_limits=LIMITS) as run:
            async for node in run:
                if Agent.is_model_request_node(node):
                    for part in node.request.parts:
                        if isinstance(part, ToolReturnPart):
                            log_event(name, "tool_result", deps.ticket_id, tool=part.tool_name, result=part.content)
                elif Agent.is_call_tools_node(node):
                    for part in node.model_response.parts:
                        if isinstance(part, ToolCallPart):
                            log_event(name, "tool_call", deps.ticket_id, tool=part.tool_name, args=part.args)
                        elif isinstance(part, TextPart) and part.content.strip():
                            log_event(name, "agent_note", deps.ticket_id, text=part.content)
        output = run.result.output
    except Exception as exc:  # includes UsageLimitExceeded
        log_event(name, "error", deps.ticket_id, error=f"{type(exc).__name__}: {exc}")
        raise
    log_event(
        name, "agent_output", deps.ticket_id,
        output=output.model_dump() if hasattr(output, "model_dump") else output,
        tokens=usage.total_tokens, requests=usage.requests,
    )
    log_event(name, "run_end", deps.ticket_id)
    return output
