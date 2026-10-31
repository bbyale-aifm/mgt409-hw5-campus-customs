"""Run the Boss over open tickets:  python -m backend.run_tickets [ticket_id ...]

Reset the database first with `python3 scripts/reset_db.py`.
"""
import asyncio
import json
import sys

from pydantic_ai.usage import RunUsage

from .boss import handle_ticket


async def main(ids: list[int]) -> None:
    for tid in ids:
        usage = RunUsage()
        outcome = await handle_ticket(tid, usage)
        print(json.dumps(outcome.model_dump(), indent=2))
        print(f"-- ticket {tid}: {usage.total_tokens} tokens, {usage.requests} requests")


if __name__ == "__main__":
    asyncio.run(main([int(a) for a in sys.argv[1:]] or [101, 102, 103]))
