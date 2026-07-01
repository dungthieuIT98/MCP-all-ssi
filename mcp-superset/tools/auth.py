"""Authentication tools for Superset MCP."""
from __future__ import annotations

from typing import Any, Dict, Optional

from mcp.server.fastmcp import Context

from _mcp import mcp
from client import (
    SupersetContext,
    authenticate_user as client_authenticate,
    get_superset_context,
    refresh_access_token as client_refresh_token,
)
from utils.api import get_csrf_token
from utils.decorators import handle_api_errors
from utils.constants import USER_ME


def _check_token_valid(ctx: Context) -> Dict[str, Any]:
    """Check if current token is valid."""
    superset_ctx = get_superset_context(ctx)
    if not superset_ctx.access_token:
        return {"valid": False, "error": "No access token available"}

    try:
        response = superset_ctx.client.get(USER_ME)
        if response.status_code == 200:
            return {"valid": True}
        return {"valid": False, "status_code": response.status_code, "error": response.text}
    except Exception as e:
        return {"valid": False, "error": str(e)}


@mcp.tool()
@handle_api_errors
async def superset_auth_check_token_validity(ctx: Context) -> Dict[str, Any]:
    """Check if the current access token is still valid."""
    return _check_token_valid(ctx)


@mcp.tool()
@handle_api_errors
async def superset_auth_refresh_token(ctx: Context) -> Dict[str, Any]:
    """Refresh the access token."""
    superset_ctx = get_superset_context(ctx)
    return await client_refresh_token(superset_ctx)


@mcp.tool()
@handle_api_errors
async def superset_auth_authenticate_user(
    ctx: Context,
    username: Optional[str] = None,
    password: Optional[str] = None,
    refresh: bool = True,
) -> Dict[str, Any]:
    """Authenticate with Superset and get access token."""
    superset_ctx = get_superset_context(ctx)

    # Check existing token
    if superset_ctx.access_token:
        validity = _check_token_valid(ctx)
        if validity.get("valid"):
            return {"message": "Already authenticated with valid token", "access_token": superset_ctx.access_token}

        if refresh:
            refresh_result = await client_refresh_token(superset_ctx)
            if not refresh_result.get("error"):
                return refresh_result

    result = await client_authenticate(superset_ctx, username, password)
    if not result.get("error"):
        await get_csrf_token(ctx)

    return result
