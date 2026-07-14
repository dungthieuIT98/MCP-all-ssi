"""API helper functions for Superset MCP."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from mcp.server.fastmcp import Context

from client import get_caller_session, get_caller_token, get_superset_context
from utils.constants import AUTH_CSRF

logger = logging.getLogger(__name__)


def _auth_headers(ctx: Context) -> Optional[Dict[str, str]]:
    """Build auth headers for a Superset call from the caller's credentials.

    Prefers a per-user Bearer token (JWT). Falls back to forwarding the caller's
    Flask ``session`` cookie, which is the only credential an Azure/OAuth user
    has — the JWT login endpoint does not support OAuth. Returns None when the
    caller presented neither (unauthenticated).
    """
    token = get_caller_token(ctx)
    if token:
        return {"Authorization": f"Bearer {token}"}
    session = get_caller_session(ctx)
    if session:
        return {"Cookie": f"session={session}"}
    return None


async def get_csrf_token(ctx: Context) -> Optional[str]:
    """Get a CSRF token from Superset, authenticating as the caller.

    CSRF issuance itself requires an authenticated session, so we forward the
    caller's own credential (Bearer or session cookie) on this request too.
    """
    superset_ctx = get_superset_context(ctx)
    client = superset_ctx.client

    auth = _auth_headers(ctx)
    try:
        response = await client.get(AUTH_CSRF, headers=auth or {})
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


async def make_api_request(
    ctx: Context,
    method: str,
    endpoint: str,
    data: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Make an API request to Superset using the caller's own credential.

    The caller's forwarded credential — a Bearer JWT, or (for Azure/OAuth users)
    the Flask ``session`` cookie — is the only credential used. A 401 is surfaced
    to the caller to re-authenticate; the server never falls back to a shared
    service account.
    """
    superset_ctx = get_superset_context(ctx)
    client = superset_ctx.client
    auth = _auth_headers(ctx)

    if auth is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Not authenticated")

    # Get CSRF token for non-GET requests
    if method.lower() != "get" and not superset_ctx.csrf_token:
        await get_csrf_token(ctx)

    headers = dict(auth)
    if method.lower() != "get" and superset_ctx.csrf_token:
        headers["X-CSRFToken"] = superset_ctx.csrf_token

    if method.lower() == "get":
        response = await client.get(endpoint, params=params, headers=headers)
    elif method.lower() == "post":
        response = await client.post(endpoint, json=data, params=params, headers=headers)
    elif method.lower() == "put":
        response = await client.put(endpoint, json=data, headers=headers)
    elif method.lower() == "delete":
        response = await client.delete(endpoint, headers=headers)
    else:
        raise ValueError(f"Unsupported HTTP method: {method}")

    if response.status_code not in [200, 201]:
        return {"error": f"API request failed: {response.status_code} - {response.text}"}

    # Handle empty responses (e.g., 204 No Content)
    if not response.text:
        return {"success": True}

    return response.json()


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
