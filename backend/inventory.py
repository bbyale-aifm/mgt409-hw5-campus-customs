"""The inventory agent."""
from functools import lru_cache

from .agent_base import build_agent
from .delegation import add_specialist_tools
from .models import SpecialistReport


@lru_cache
def get_agent():
    agent = build_agent("inventory", SpecialistReport)
    add_specialist_tools(agent, "inventory")
    return agent
