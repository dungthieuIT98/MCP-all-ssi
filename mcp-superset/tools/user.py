"""User and activity tools for Superset MCP."""
from __future__ import annotations

from typing import Any, Dict

from mcp.server.fastmcp import Context

from _mcp import mcp

from utils.api import make_api_request
from utils.decorators import handle_api_errors, requires_auth
from utils.constants import ACTIVITY_RECENT, USER_ME, USER_ROLES


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_user_get_current(ctx: Context) -> Dict[str, Any]:
    """Get information about the currently authenticated user."""
    return await make_api_request(ctx, "get", USER_ME)


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_user_get_roles(ctx: Context) -> Dict[str, Any]:
    """Get roles for the current user."""
    return await make_api_request(ctx, "get", USER_ROLES)


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_activity_get_recent(ctx: Context) -> Dict[str, Any]:
    """Get recent activity data for the current user."""
    return await make_api_request(ctx, "get", ACTIVITY_RECENT)
