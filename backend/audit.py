"""Append-only audit trail at output/audit_trail.json (a JSON array of events).

Existing entries are always preserved: each append re-reads the file under a
lock, adds one event, and replaces the file atomically.
"""
import fcntl
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from common.config import ROOT

AUDIT_PATH = Path(os.environ.get("AUDIT_TRAIL_PATH", ROOT / "output" / "audit_trail.json"))


def log_event(agent: str, event: str, ticket_id: int | None = None, **details) -> dict:
    """Append one event. event is one of: run_start, tool_call, tool_result,
    handoff, delegation, agent_output, run_end, error.
    """
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lock_path = AUDIT_PATH.with_suffix(".lock")
    with open(lock_path, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        events = json.loads(AUDIT_PATH.read_text() or "[]") if AUDIT_PATH.exists() else []
        entry = {
            "seq": len(events) + 1,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "ticket_id": ticket_id,
            "agent": agent,
            "event": event,
            **details,
        }
        events.append(entry)
        fd, tmp = tempfile.mkstemp(dir=AUDIT_PATH.parent, suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            json.dump(events, f, indent=2, default=str)
        os.replace(tmp, AUDIT_PATH)
    return entry


def read_events(ticket_id: int | None = None, since_seq: int = 0) -> list[dict]:
    """Read events (optionally one ticket's, and only those after since_seq)."""
    if not AUDIT_PATH.exists():
        return []
    events = json.loads(AUDIT_PATH.read_text() or "[]")
    return [e for e in events if e["seq"] > since_seq and (ticket_id is None or e.get("ticket_id") == ticket_id)]
