"""Explore tools for Superset MCP."""
from __future__ import annotations

from typing import Any, Dict

from mcp.server.fastmcp import Context

from _mcp import mcp

from utils.api import make_api_request
from utils.decorators import handle_api_errors, requires_auth
from utils.constants import EXPLORE_FORM_DATA, EXPLORE_PERMALINK


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_explore_form_data_create(
    ctx: Context, form_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Create form data for chart exploration."""
    return await make_api_request(ctx, "post", EXPLORE_FORM_DATA, data=form_data)


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_explore_form_data_get(ctx: Context, key: str) -> Dict[str, Any]:
    """Get form data for chart exploration."""
    return await make_api_request(ctx, "get", f"{EXPLORE_FORM_DATA}/{key}")


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_explore_permalink_create(
    ctx: Context, state: Dict[str, Any]
) -> Dict[str, Any]:
    """Create a permalink for chart exploration."""
    return await make_api_request(ctx, "post", EXPLORE_PERMALINK, data=state)


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_explore_permalink_get(ctx: Context, key: str) -> Dict[str, Any]:
    """Get a permalink for chart exploration."""
    return await make_api_request(ctx, "get", f"{EXPLORE_PERMALINK}/{key}")
