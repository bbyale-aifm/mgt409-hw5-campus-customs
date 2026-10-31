"""Shared construction for the five agents: model, prompt, MCP tools."""
import os
from pathlib import Path

from openai import AsyncOpenAI
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

from common.config import MODEL, PORTKEY_BASE_URL, portkey_api_key

from .mcp_client import toolset_for
from .models import Deps

PROMPTS = Path(__file__).parent / "prompts"


def make_model() -> OpenAIResponsesModel:
    """The configured model (default gpt-6-luna) reached through Portkey."""
    key = portkey_api_key()
    headers = {"x-portkey-api-key": key}  # Portkey reads its own key from this header
    if os.environ.get("PORTKEY_PROVIDER"):  # optional: which provider Portkey should route to
        headers["x-portkey-provider"] = os.environ["PORTKEY_PROVIDER"]
    client = AsyncOpenAI(base_url=PORTKEY_BASE_URL, api_key=key, default_headers=headers)
    return OpenAIResponsesModel(MODEL, provider=OpenAIProvider(openai_client=client))


def build_agent(name: str, output_type: type, model=None) -> Agent[Deps, object]:
    return Agent(
        model or make_model(),
        deps_type=Deps,
        output_type=output_type,
        instructions=(PROMPTS / f"{name}.md").read_text(),
        toolsets=[toolset_for(name)],
        name=name,
        retries=2,
    )
