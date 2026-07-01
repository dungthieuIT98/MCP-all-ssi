"""Chart tools for Superset MCP."""
from __future__ import annotations

import json
from typing import Any, Dict

from mcp.server.fastmcp import Context

from _mcp import mcp

from utils.api import delete_with_confirmation_async, make_api_request
from utils.decorators import handle_api_errors, requires_auth
from utils.constants import CHART_BASE


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_chart_list(ctx: Context) -> Dict[str, Any]:
    """Get a list of charts from Superset."""
    return await make_api_request(ctx, "get", CHART_BASE)


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_chart_get_by_id(ctx: Context, chart_id: int) -> Dict[str, Any]:
    """Get details for a specific chart."""
    return await make_api_request(ctx, "get", f"{CHART_BASE}/{chart_id}")


# @mcp.tool()
# async def superset_chart_create(...): hidden — read-only mode

# @mcp.tool()
# async def superset_chart_update(...): hidden — read-only mode

# @mcp.tool()
# async def superset_chart_delete(...): hidden — read-only mode
