"""Database tools for Superset MCP."""
from __future__ import annotations

from typing import Any, Dict

from mcp.server.fastmcp import Context

from _mcp import mcp

from utils.api import delete_with_confirmation_async, make_api_request
from utils.decorators import handle_api_errors, requires_auth
from utils.constants import (
    DATABASE_BASE,
    DATABASE_TEST,
    DATABASE_VALIDATE_SQL,
    DATABASE_VALIDATE_PARAMS,
)


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_database_list(ctx: Context) -> Dict[str, Any]:
    """Get a list of databases from Superset."""
    return await make_api_request(ctx, "get", DATABASE_BASE)


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_database_get_by_id(ctx: Context, database_id: int) -> Dict[str, Any]:
    """Get details for a specific database."""
    return await make_api_request(ctx, "get", f"{DATABASE_BASE}/{database_id}")


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_database_create(
    ctx: Context,
    engine: str,
    configuration_method: str,
    database_name: str,
    sqlalchemy_uri: str,
) -> Dict[str, Any]:
    """Create a new database connection in Superset."""
    payload = {
        "engine": engine,
        "configuration_method": configuration_method,
        "database_name": database_name,
        "sqlalchemy_uri": sqlalchemy_uri,
        "allow_dml": True,
        "allow_cvas": True,
        "allow_ctas": True,
        "expose_in_sqllab": True,
    }
    return await make_api_request(ctx, "post", DATABASE_BASE, data=payload)


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_database_get_tables(ctx: Context, database_id: int) -> Dict[str, Any]:
    """Get a list of tables for a given database."""
    return await make_api_request(ctx, "get", f"{DATABASE_BASE}/{database_id}/tables/")


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_database_schemas(ctx: Context, database_id: int) -> Dict[str, Any]:
    """Get schemas for a specific database."""
    return await make_api_request(ctx, "get", f"{DATABASE_BASE}/{database_id}/schemas/")


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_database_test_connection(
    ctx: Context, database_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Test a database connection."""
    return await make_api_request(ctx, "post", DATABASE_TEST, data=database_data)


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_database_update(
    ctx: Context, database_id: int, data: Dict[str, Any]
) -> Dict[str, Any]:
    """Update an existing database connection."""
    return await make_api_request(ctx, "put", f"{DATABASE_BASE}/{database_id}", data=data)


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_database_delete(ctx: Context, database_id: int) -> Dict[str, Any]:
    """Delete a database connection."""
    return await delete_with_confirmation_async(ctx, f"{DATABASE_BASE}/{database_id}", "Database", database_id)


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_database_get_catalogs(ctx: Context, database_id: int) -> Dict[str, Any]:
    """Get all catalogs from a database."""
    return await make_api_request(ctx, "get", f"{DATABASE_BASE}/{database_id}/catalogs/")


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_database_get_connection(ctx: Context, database_id: int) -> Dict[str, Any]:
    """Get database connection information."""
    return await make_api_request(ctx, "get", f"{DATABASE_BASE}/{database_id}/connection")


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_database_get_function_names(ctx: Context, database_id: int) -> Dict[str, Any]:
    """Get function names supported by a database."""
    return await make_api_request(ctx, "get", f"{DATABASE_BASE}/{database_id}/function_names/")


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_database_get_related_objects(ctx: Context, database_id: int) -> Dict[str, Any]:
    """Get charts and dashboards associated with a database."""
    return await make_api_request(ctx, "get", f"{DATABASE_BASE}/{database_id}/related_objects/")


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_database_validate_sql(
    ctx: Context, database_id: int, sql: str
) -> Dict[str, Any]:
    """Validate arbitrary SQL against a database."""
    return await make_api_request(
        ctx, "post", f"{DATABASE_BASE}/{database_id}/validate_sql/", data={"sql": sql}
    )


@mcp.tool()
@requires_auth
@handle_api_errors
async def superset_database_validate_parameters(
    ctx: Context, parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """Validate database connection parameters."""
    return await make_api_request(ctx, "post", DATABASE_VALIDATE_PARAMS, data=parameters)
