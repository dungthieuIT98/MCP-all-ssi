"""SQL Lab tools for Superset MCP."""
from __future__ import annotations

from typing import Any, Dict, Optional

from mcp.server.fastmcp import Context

from _mcp import mcp

from client import get_superset_context
from utils.api import get_csrf_token, make_api_request
from utils.decorators import handle_api_errors, requires_auth
from utils.constants import (
    SQLLAB_BASE,
    SQLLAB_EXECUTE,
    SQLLAB_FORMAT,
    SQLLAB_RESULTS,
    SQLLAB_ESTIMATE,
    SAVED_QUERY_BASE,
)


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_sqllab_execute_query(
    ctx: Context, database_id: int, sql: str
) -> Dict[str, Any]:
    """Execute a SQL query in SQL Lab."""
    superset_ctx = get_superset_context(ctx)
    if not superset_ctx.csrf_token:
        await get_csrf_token(ctx)

    payload = {
        "database_id": database_id,
        "sql": sql,
        "schema": "",
        "tab": "MCP Query",
        "runAsync": False,
        "select_as_cta": False,
    }
    return await make_api_request(ctx, "post", SQLLAB_EXECUTE, data=payload)


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_sqllab_get_saved_queries(ctx: Context) -> Dict[str, Any]:
    """Get a list of saved queries from SQL Lab."""
    return await make_api_request(ctx, "get", SAVED_QUERY_BASE)


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_sqllab_format_sql(ctx: Context, sql: str) -> Dict[str, Any]:
    """Format a SQL query for better readability."""
    return await make_api_request(ctx, "post", SQLLAB_FORMAT, data={"sql": sql})


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_sqllab_get_results(ctx: Context, key: str) -> Dict[str, Any]:
    """Get results of a previously executed SQL query."""
    return await make_api_request(ctx, "get", SQLLAB_RESULTS, params={"key": key})


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_sqllab_estimate_query_cost(
    ctx: Context, database_id: int, sql: str, schema: Optional[str] = None
) -> Dict[str, Any]:
    """Estimate the cost of executing a SQL query."""
    payload: Dict[str, Any] = {"database_id": database_id, "sql": sql}
    if schema:
        payload["schema"] = schema
    return await make_api_request(ctx, "post", SQLLAB_ESTIMATE, data=payload)


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_sqllab_export_query_results(
    ctx: Context, client_id: str
) -> Dict[str, Any]:
    """Export the results of a SQL query to CSV."""
    superset_ctx = get_superset_context(ctx)
    try:
        response = await superset_ctx.client.get(f"{SQLLAB_BASE}/export/{client_id}")
        if response.status_code != 200:
            return {"error": f"Failed to export: {response.status_code} - {response.text}"}
        return {"message": "Query results exported successfully", "data": response.text}
    except Exception as e:
        return {"error": f"Error exporting query results: {e}"}


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_sqllab_get_bootstrap_data(ctx: Context) -> Dict[str, Any]:
    """Get the bootstrap data for SQL Lab."""
    return await make_api_request(ctx, "get", SQLLAB_BASE)
