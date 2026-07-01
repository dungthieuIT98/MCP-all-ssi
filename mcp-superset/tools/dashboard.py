"""Dashboard tools for Superset MCP."""
from __future__ import annotations

from typing import Any, Dict

from mcp.server.fastmcp import Context

from _mcp import mcp

from utils.api import delete_with_confirmation_async, make_api_request
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


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_dashboard_create(
    ctx: Context, dashboard_title: str, json_metadata: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Create a new dashboard in Superset."""
    payload: Dict[str, Any] = {"dashboard_title": dashboard_title}
    if json_metadata:
        payload["json_metadata"] = json_metadata
    return await make_api_request(ctx, "post", DASHBOARD_BASE, data=payload)


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_dashboard_update(
    ctx: Context, dashboard_id: int, data: Dict[str, Any]
) -> Dict[str, Any]:
    """Update an existing dashboard."""
    return await make_api_request(ctx, "put", f"{DASHBOARD_BASE}/{dashboard_id}", data=data)


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_dashboard_delete(ctx: Context, dashboard_id: int) -> Dict[str, Any]:
    """Delete a dashboard."""
    return await delete_with_confirmation_async(ctx, f"{DASHBOARD_BASE}/{dashboard_id}", "Dashboard", dashboard_id)
