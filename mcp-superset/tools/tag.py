"""Tag tools for Superset MCP."""
from __future__ import annotations

from typing import Any, Dict

from mcp.server.fastmcp import Context

from core.server import mcp

from utils.http import make_api_request
from utils.decorators import handle_api_errors, requires_auth
from utils.constants import TAG_BASE, TAG_GET_OBJECTS


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_tag_list(ctx: Context) -> Dict[str, Any]:
    """Get a list of tags from Superset."""
    return await make_api_request(ctx, "get", TAG_BASE)


# @mcp.tool()
# async def superset_tag_create(...): hidden — read-only mode

@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_tag_get_by_id(ctx: Context, tag_id: int) -> Dict[str, Any]:
    """Get details for a specific tag."""
    return await make_api_request(ctx, "get", f"{TAG_BASE}/{tag_id}")


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_tag_objects(ctx: Context) -> Dict[str, Any]:
    """Get objects associated with tags."""
    return await make_api_request(ctx, "get", TAG_GET_OBJECTS)


# @mcp.tool()
# async def superset_tag_delete(...): hidden — read-only mode

# @mcp.tool()
# async def superset_tag_object_add(...): hidden — read-only mode

# @mcp.tool()
# async def superset_tag_object_remove(...): hidden — read-only mode
