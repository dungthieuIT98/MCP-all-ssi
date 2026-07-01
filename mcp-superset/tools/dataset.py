"""Dataset tools for Superset MCP."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import Context

from _mcp import mcp

from utils.api import make_api_request
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


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_dataset_create(
    ctx: Context,
    table_name: str,
    database_id: int,
    schema: Optional[str] = None,
    owners: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Create a new dataset in Superset."""
    payload: Dict[str, Any] = {"table_name": table_name, "database": database_id}
    if schema:
        payload["schema"] = schema
    if owners:
        payload["owners"] = owners
    return await make_api_request(ctx, "post", DATASET_BASE, data=payload)
