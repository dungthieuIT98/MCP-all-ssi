"""Dashboard tools for Superset MCP."""
from __future__ import annotations

from typing import Any, Dict

from mcp.server.fastmcp import Context

from core.server import mcp

from utils.http import make_api_request
from utils.decorators import handle_api_errors, requires_auth
from utils.constants import DASHBOARD_BASE


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_dashboard_list(ctx: Context) -> Dict[str, Any]:
    """Get a list of dashboards from Superset."""
    return await make_api_request(ctx, "get", DASHBOARD_BASE)


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_dashboard_get_by_id(ctx: Context, dashboard_id: int) -> Dict[str, Any]:
    """Get details for a specific dashboard."""
    return await make_api_request(ctx, "get", f"{DASHBOARD_BASE}/{dashboard_id}")


# @mcp.tool()
# async def superset_dashboard_create(...): hidden — read-only mode

# @mcp.tool()
# async def superset_dashboard_update(...): hidden — read-only mode

# @mcp.tool()
# async def superset_dashboard_delete(...): hidden — read-only mode
