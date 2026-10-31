"""Human approval for payments: the only way a payment request becomes a payment.

  python scripts/approve_payment.py list
  python scripts/approve_payment.py approve <request_id> --by "Your Name"
  python scripts/approve_payment.py reject <request_id> --by "Your Name"
  python scripts/approve_payment.py list-prices
  python scripts/approve_payment.py approve-price <proposal_id> --by "Your Name"
  python scripts/approve_payment.py reject-price <proposal_id> --by "Your Name"

It talks to the MCP server (approve_payment / reject_payment); the server only
runs those tools for a process launched here, so no agent can use them.
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fastmcp import Client  # noqa: E402
from fastmcp.client.transports import StdioTransport  # noqa: E402

from common.config import DB_PATH, ROOT  # noqa: E402


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["list", "approve", "reject", "approve-price", "reject-price", "list-prices"])
    ap.add_argument("request_id", type=int, nargs="?")
    ap.add_argument("--by", default="")
    a = ap.parse_args()
    transport = StdioTransport(
        sys.executable, ["-m", "mcp_server.server"], cwd=str(ROOT),
        env={"CAMPUS_CUSTOMS_DB": str(DB_PATH.relative_to(ROOT)), "CC_HUMAN_APPROVER": "1"},
    )
    async with Client(transport) as c:
        if a.action == "list":
            call = await c.call_tool("list_payment_requests", {})
        elif a.action == "list-prices":
            call = await c.call_tool("list_price_proposals", {})
        else:
            if a.request_id is None or not a.by.strip():
                ap.error("approve/reject need a request id and --by \"Your Name\"")
            tools = {
                "approve": ("approve_payment", "request_id", "approved_by"),
                "reject": ("reject_payment", "request_id", "decided_by"),
                "approve-price": ("approve_price_proposal", "proposal_id", "approved_by"),
                "reject-price": ("reject_price_proposal", "proposal_id", "decided_by"),
            }
            tool, idkey, key = tools[a.action]
            call = await c.call_tool(tool, {idkey: a.request_id, key: a.by})
        print(json.dumps(call.data, indent=2))


asyncio.run(main())
