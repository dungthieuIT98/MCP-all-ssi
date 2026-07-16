"""Dataset tools for Superset MCP."""
from __future__ import annotations

from typing import Any, Dict

from mcp.server.fastmcp import Context

from core.server import mcp

from utils.http import make_api_request
from utils.decorators import handle_api_errors, requires_auth
from utils.constants import DATASET_BASE


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_dataset_list(ctx: Context) -> Dict[str, Any]:
    """Get a list of datasets from Superset."""
    return await make_api_request(ctx, "get", DATASET_BASE)


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_dataset_get_by_id(ctx: Context, dataset_id: int) -> Dict[str, Any]:
    """Get details for a specific dataset."""
    return await make_api_request(ctx, "get", f"{DATASET_BASE}/{dataset_id}")


# @mcp.tool()
# async def superset_dataset_create(...): hidden — read-only mode
