"""Superset client and context management."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, AsyncIterator, Dict, Optional

import httpx
from mcp.server.fastmcp import Context

from config import get_config

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)

config = get_config()


@dataclass
class SupersetContext:
    """Context for the Superset MCP server."""

    client: httpx.AsyncClient
    base_url: str
    access_token: Optional[str] = None
    csrf_token: Optional[str] = None
    app: Optional["FastAPI"] = field(default=None, repr=False)


def load_stored_token() -> Optional[str]:
    """Load stored access token from file."""
    try:
        if os.path.exists(config.token_store_path):
            with open(config.token_store_path, "r") as f:
                return f.read().strip()
    except OSError:
        return None
    return None


def save_access_token(token: str) -> None:
    """Save access token to file."""
    try:
        with open(config.token_store_path, "w") as f:
            f.write(token)
    except OSError as e:
        logger.warning(f"Could not save access token: {e}")


def get_superset_context(ctx: Context) -> SupersetContext:
    """Get SupersetContext from MCP Context."""
    return ctx.request_context.lifespan_context


def get_caller_token(ctx: Context) -> Optional[str]:
    """Extract the caller's Bearer token from the incoming HTTP request.

    In streamable-http mode the MCP SDK sets request_context.request to the
    Starlette Request, so we can read the per-user Authorization header the
    auth-proxy forwards. This is the per-user Superset JWT — using it (instead of
    the shared admin token) preserves the real user's identity, roles, and RLS.
    Returns None when no request/header is available (e.g. stdio mode).
    """
    try:
        request = ctx.request_context.request
        if request is None:
            return None
        auth = request.headers.get("authorization", "")
    except (AttributeError, LookupError):
        return None
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return None


async def create_superset_context() -> SupersetContext:
    """Create a new SupersetContext with HTTP client."""
    from utils.constants import USER_ME

    client = httpx.AsyncClient(base_url=config.base_url, timeout=30.0, follow_redirects=True)
    ctx = SupersetContext(
        client=client,
        base_url=config.base_url,
    )

    # Try to load existing token
    stored_token = load_stored_token()
    if stored_token:
        ctx.access_token = stored_token
        client.headers.update({"Authorization": f"Bearer {stored_token}"})
        logger.info("Using stored access token")

        # Verify token validity
        try:
            response = await client.get(USER_ME)
            if response.status_code != 200:
                logger.info(f"Stored token invalid (status {response.status_code})")
                ctx.access_token = None
                client.headers.pop("Authorization", None)
        except Exception as e:
            logger.info(f"Error verifying stored token: {e}")
            ctx.access_token = None
            client.headers.pop("Authorization", None)

    # Auto-login with credentials from env if no valid token
    if not ctx.access_token and config.username and config.password:
        logger.info("No valid token found, authenticating with credentials...")
        result = await authenticate_user(ctx, config.username, config.password)
        if "error" in result:
            logger.warning(f"Auto-login failed: {result['error']}")
        else:
            logger.info("Auto-login successful")

    return ctx


async def close_superset_context(ctx: SupersetContext) -> None:
    """Close HTTP client and cleanup."""
    await ctx.client.aclose()


async def lifespan_manager(
    server: Any,
) -> AsyncIterator[SupersetContext]:
    """Manage Superset context lifecycle."""
    logger.info("Initializing Superset context...")
    ctx = await create_superset_context()
    try:
        yield ctx
    finally:
        logger.info("Shutting down Superset context...")
        await close_superset_context(ctx)


async def refresh_access_token(ctx: SupersetContext) -> Dict[str, Any]:
    """Refresh the access token."""
    from utils.constants import AUTH_REFRESH

    if not ctx.access_token:
        return {"error": "No access token to refresh"}

    try:
        response = await ctx.client.post(AUTH_REFRESH)
        if response.status_code != 200:
            return {"error": f"Failed to refresh token: {response.status_code}"}

        data = response.json()
        access_token = data.get("access_token")
        if not access_token:
            return {"error": "No access token returned from refresh"}

        save_access_token(access_token)
        ctx.access_token = access_token
        ctx.client.headers.update({"Authorization": f"Bearer {access_token}"})

        return {"message": "Successfully refreshed access token", "access_token": access_token}
    except Exception as e:
        return {"error": f"Error refreshing token: {e}"}


async def authenticate_user(
    ctx: SupersetContext,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> Dict[str, Any]:
    """Authenticate with Superset and get access token."""
    from utils.constants import AUTH_LOGIN

    username = username or config.username
    password = password or config.password

    if not username or not password:
        return {"error": "Username and password required"}

    try:
        response = await ctx.client.post(
            AUTH_LOGIN,
            json={"username": username, "password": password, "provider": "db", "refresh": True},
        )
        if response.status_code != 200:
            return {"error": f"Failed to authenticate: {response.status_code}"}

        data = response.json()
        access_token = data.get("access_token")
        if not access_token:
            return {"error": "No access token returned"}

        save_access_token(access_token)
        ctx.access_token = access_token
        ctx.client.headers.update({"Authorization": f"Bearer {access_token}"})

        return {"message": "Successfully authenticated", "access_token": access_token}
    except Exception as e:
        return {"error": f"Authentication error: {e}"}
