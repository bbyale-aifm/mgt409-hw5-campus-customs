"""Shared settings: the active database, the model, and Portkey wiring.

The MCP server and the FastAPI backend both import DB_PATH from here, so
data/campus_customs.db (the original) is never written to.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
ORIGINAL_DB = ROOT / "data" / "campus_customs.db"
DB_PATH = ROOT / os.environ.get("CAMPUS_CUSTOMS_DB", "data/campus_customs_new.db")
if DB_PATH.resolve() == ORIGINAL_DB.resolve():
    raise RuntimeError("Refusing to use the original database; use campus_customs_new.db")

MODEL = os.environ.get("OPENAI_MODEL", "gpt-6-luna")  # every agent, via Portkey
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"


def portkey_api_key() -> str:
    key = os.environ.get("PORTKEY_API_KEY", "")
    if not key:
        raise RuntimeError("PORTKEY_API_KEY is not set")
    return key
