"""The only door to the shop's data: the Campus Customs MCP server.

Each agent gets a view of the server limited to the tools its role needs.
There is no other tools layer, and no agent is given approve_payment or
reject_payment (humans use scripts/approve_payment.py).
"""
import sys

from fastmcp.client import Client
from fastmcp.client.transports import StdioTransport
from pydantic_ai.mcp import MCPToolset

from common.config import DB_PATH, ROOT

READ_COMMON = ["get_today", "get_ticket", "list_open_tickets"]

TOOLS_BY_AGENT: dict[str, list[str]] = {
    "boss": [*READ_COMMON, "list_payment_requests", "list_restock_requests", "list_message_drafts", "list_price_proposals", "update_ticket"],
    "inventory": [
        *READ_COMMON, "check_stock", "list_inventory", "list_vendors", "list_invoices",
        "create_restock_request", "list_restock_requests",
    ],
    "accounting": [
        *READ_COMMON, "get_pricing", "check_discount", "list_invoices", "get_cash_balance", "list_payments",
        "list_payment_requests", "request_payment", "propose_price_override", "get_lease",
    ],
    "facilities": [*READ_COMMON, "get_lease", "get_cash_balance", "list_payment_requests"],
    "customer_service": [
        *READ_COMMON, "check_stock", "get_pricing", "list_vendors", "list_restock_requests",
        "list_payment_requests", "list_message_drafts", "draft_customer_message",
    ],
}

_toolset: MCPToolset | None = None


def _shared_toolset() -> MCPToolset:
    """One stdio server process shared by all agents (launched without the human-approver flag)."""
    global _toolset
    if _toolset is None:
        transport = StdioTransport(
            command=sys.executable,
            args=["-m", "mcp_server.server"],
            env={"CAMPUS_CUSTOMS_DB": str(DB_PATH.relative_to(ROOT))},
            cwd=str(ROOT),
        )
        _toolset = MCPToolset(Client(transport))
    return _toolset


def toolset_for(agent_name: str):
    allowed = set(TOOLS_BY_AGENT[agent_name])
    return _shared_toolset().filtered(lambda ctx, tool: tool.name in allowed)
