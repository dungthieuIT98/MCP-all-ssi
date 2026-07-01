"""Tag tools for Superset MCP."""
from __future__ import annotations

from typing import Any, Dict

from mcp.server.fastmcp import Context

from _mcp import mcp

from utils.api import delete_with_confirmation_async, make_api_request
from utils.decorators import handle_api_errors, requires_auth
from utils.constants import TAG_BASE, TAG_OBJECTS, TAG_GET_OBJECTS


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


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_tag_delete(ctx: Context, tag_id: int) -> Dict[str, Any]:
    """Delete a tag."""
    return await delete_with_confirmation_async(ctx, f"{TAG_BASE}/{tag_id}", "Tag", tag_id)


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_tag_object_add(
    ctx: Context, object_type: str, object_id: int, tag_name: str
) -> Dict[str, Any]:
    """Add a tag to an object."""
    payload = {"object_type": object_type, "object_id": object_id, "tag_name": tag_name}
    return await make_api_request(ctx, "post", TAG_OBJECTS, data=payload)


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_tag_object_remove(
    ctx: Context, object_type: str, object_id: int, tag_name: str
) -> Dict[str, Any]:
    """Remove a tag from an object."""
    response = await make_api_request(
        ctx, "delete", f"{TAG_BASE}/{object_type}/{object_id}", params={"tag_name": tag_name}
    )
    if not response.get("error"):
        return {"message": f"Tag '{tag_name}' removed from {object_type} {object_id} successfully"}
    return response
