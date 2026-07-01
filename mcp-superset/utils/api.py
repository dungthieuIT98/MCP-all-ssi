"""API helper functions for Superset MCP."""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict, Optional

import httpx
from mcp.server.fastmcp import Context

from client import (
    SupersetContext,
    authenticate_user,
    get_superset_context,
    refresh_access_token,
)
from utils.constants import AUTH_CSRF

logger = logging.getLogger(__name__)


async def get_csrf_token(ctx: Context) -> Optional[str]:
    """Get a CSRF token from Superset."""
    superset_ctx = get_superset_context(ctx)
    client = superset_ctx.client

    try:
        response = await client.get(AUTH_CSRF)
        if response.status_code == 200:
            data = response.json()
            csrf_token = data.get("result")
            superset_ctx.csrf_token = csrf_token
            return csrf_token
        logger.info(f"Failed to get CSRF token: {response.status_code} - {response.text}")
        return None
    except Exception as e:
        logger.info(f"Error getting CSRF token: {e}")
        return None


async def with_auto_refresh(
    ctx: Context, api_call: Callable[[], Awaitable[httpx.Response]]
) -> httpx.Response:
    """Execute API call with automatic token refresh on 401."""
    superset_ctx = get_superset_context(ctx)

    if not superset_ctx.access_token:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Not authenticated")

    # First attempt
    try:
        response = await api_call()
        if response.status_code != 401:
            return response
    except httpx.HTTPStatusError as e:
        if e.response.status_code != 401:
            raise e
        response = e.response
    except Exception:
        raise

    # Token expired, try refresh
    logger.info("Received 401 Unauthorized. Attempting to refresh token...")
    refresh_result = await refresh_access_token(superset_ctx)

    if refresh_result.get("error"):
        logger.info(f"Token refresh failed: {refresh_result.get('error')}. Re-authenticating...")
        auth_result = await authenticate_user(superset_ctx)
        if auth_result.get("error"):
            from fastapi import HTTPException

            raise HTTPException(status_code=401, detail="Authentication failed")

    # Retry with new token
    return await api_call()


async def make_api_request(
    ctx: Context,
    method: str,
    endpoint: str,
    data: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    auto_refresh: bool = True,
) -> Dict[str, Any]:
    """Make an API request to Superset with optional auto-refresh."""
    superset_ctx = get_superset_context(ctx)
    client = superset_ctx.client

    # Get CSRF token for non-GET requests
    if method.lower() != "get" and not superset_ctx.csrf_token:
        await get_csrf_token(ctx)

    async def make_request() -> httpx.Response:
        headers = {}
        if method.lower() != "get" and superset_ctx.csrf_token:
            headers["X-CSRFToken"] = superset_ctx.csrf_token

        if method.lower() == "get":
            return await client.get(endpoint, params=params)
        elif method.lower() == "post":
            return await client.post(endpoint, json=data, params=params, headers=headers)
        elif method.lower() == "put":
            return await client.put(endpoint, json=data, headers=headers)
        elif method.lower() == "delete":
            return await client.delete(endpoint, headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

    if auto_refresh:
        response = await with_auto_refresh(ctx, make_request)
    else:
        response = await make_request()

    if response.status_code not in [200, 201]:
        return {"error": f"API request failed: {response.status_code} - {response.text}"}

    # Handle empty responses (e.g., 204 No Content)
    if not response.text:
        return {"success": True}

    return response.json()


def delete_with_confirmation(
    ctx: Context,
    endpoint: str,
    entity_name: str,
    entity_id: Any,
) -> Dict[str, Any]:
    """Helper for delete operations with consistent success message."""
    # Note: This is sync wrapper - in practice tools use await make_api_request
    # This function is kept for interface consistency
    return {"error": "Use await delete_with_confirmation_async instead"}


async def delete_with_confirmation_async(
    ctx: Context,
    endpoint: str,
    entity_name: str,
    entity_id: Any,
) -> Dict[str, Any]:
    """Helper for delete operations with consistent success message."""
    response = await make_api_request(ctx, "delete", endpoint)
    if not response.get("error"):
        return {"message": f"{entity_name} {entity_id} deleted successfully"}
    return response
