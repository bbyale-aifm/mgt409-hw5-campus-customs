"""Smoke test: call each MCP tool through a real FastMCP client."""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fastmcp import Client  # noqa: E402

from mcp_server.server import mcp  # noqa: E402

CALLS = [
    ("check_stock", {"sku": "CC-TEE-WHITE", "size": "S"}),  # ticket 101
    ("get_lease", {"lease_id": 1}),  # ticket 102
    ("get_pricing", {"sku": "CC-HOOD-NAVY"}),  # ticket 103
    ("check_stock", {"sku": "NOPE", "size": "S"}),
]


async def main() -> None:
    async with Client(mcp) as client:
        print("tools:", [t.name for t in await client.list_tools()])
        for name, args in CALLS:
            result = await client.call_tool(name, args)
            print(name, args, "->", json.dumps(result.data))


asyncio.run(main())
