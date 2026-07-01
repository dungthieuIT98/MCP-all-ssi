"""Query tools for Superset MCP."""
from __future__ import annotations

from typing import Any, Dict

from mcp.server.fastmcp import Context

from _mcp import mcp

from utils.api import make_api_request
from utils.decorators import handle_api_errors, requires_auth
from utils.constants import QUERY_BASE, QUERY_STOP


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_query_list(ctx: Context) -> Dict[str, Any]:
    """Get a list of queries from Superset."""
    return await make_api_request(ctx, "get", QUERY_BASE)


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_query_get_by_id(ctx: Context, query_id: int) -> Dict[str, Any]:
    """Get details for a specific query."""
    return await make_api_request(ctx, "get", f"{QUERY_BASE}/{query_id}")


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_query_stop(ctx: Context, client_id: str) -> Dict[str, Any]:
    """Stop a running query."""
    return await make_api_request(ctx, "post", QUERY_STOP, data={"client_id": client_id})
