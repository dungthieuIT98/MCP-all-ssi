"""System tools for Superset MCP."""
from __future__ import annotations

from typing import Any, Dict

from mcp.server.fastmcp import Context

from _mcp import mcp

from client import get_superset_context
from utils.api import make_api_request
from utils.decorators import handle_api_errors, requires_auth
from utils.constants import MENU, ADVANCED_DATA_TYPE


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_menu_get(ctx: Context) -> Dict[str, Any]:
    """Get the Superset menu data."""
    return await make_api_request(ctx, "get", MENU)


@mcp.tool()
@handle_api_errors
async def superset_config_get_base_url(ctx: Context) -> Dict[str, Any]:
    """Get the base URL of the Superset instance."""
    superset_ctx = get_superset_context(ctx)
    return {"base_url": superset_ctx.base_url, "message": f"Connected to Superset at: {superset_ctx.base_url}"}


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_advanced_data_type_convert(
    ctx: Context, type_name: str, value: Any
) -> Dict[str, Any]:
    """Convert a value to an advanced data type."""
    return await make_api_request(
        ctx, "get", f"{ADVANCED_DATA_TYPE}/convert", params={"type_name": type_name, "value": value}
    )


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_advanced_data_type_list(ctx: Context) -> Dict[str, Any]:
    """Get list of available advanced data types."""
    return await make_api_request(ctx, "get", f"{ADVANCED_DATA_TYPE}/types")
