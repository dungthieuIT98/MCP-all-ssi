"""Saved query tools for Superset MCP."""
from __future__ import annotations

from typing import Any, Dict

from mcp.server.fastmcp import Context

from _mcp import mcp

from utils.api import make_api_request
from utils.decorators import handle_api_errors, requires_auth
from utils.constants import SAVED_QUERY_BASE


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_saved_query_get_by_id(ctx: Context, query_id: int) -> Dict[str, Any]:
    """Get details for a specific saved query."""
    return await make_api_request(ctx, "get", f"{SAVED_QUERY_BASE}/{query_id}")


# @mcp.tool()
# async def superset_saved_query_create(...): hidden — read-only mode
