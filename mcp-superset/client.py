"""Superset client and context management."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, AsyncIterator, Optional

import httpx
from mcp.server.fastmcp import Context

from config import get_config

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)

config = get_config()


@dataclass
class SupersetContext:
    """Context for the Superset MCP server.

    Holds only the shared HTTP client and base URL. There is no service-account
    token here by design: every request carries the caller's own per-user token
    (see get_caller_token), so the server never authenticates as a shared account.
    """

    client: httpx.AsyncClient
    base_url: str
    csrf_token: Optional[str] = None
    app: Optional["FastAPI"] = field(default=None, repr=False)


def get_superset_context(ctx: Context) -> SupersetContext:
    """Get SupersetContext from MCP Context."""
    return ctx.request_context.lifespan_context


def get_caller_token(ctx: Context) -> Optional[str]:
    """Extract the caller's Bearer token from the incoming HTTP request.

    In streamable-http mode the MCP SDK sets request_context.request to the
    Starlette Request, so we can read the per-user Authorization header the
    auth-proxy forwards. This is the per-user Superset JWT — it carries the real
    user's identity, roles, and RLS into every Superset call.
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


def get_caller_session(ctx: Context) -> Optional[str]:
    """Extract the caller's Superset session cookie from the incoming request.

    Superset issues a Flask ``session`` cookie after any successful web login —
    including Azure AD / OAuth, which the JWT ``/security/login`` endpoint does
    NOT support. Superset's own REST API accepts that session cookie (plus a
    CSRF token for writes), so forwarding it lets an OAuth-authenticated user
    drive the API with their real identity and RLS, no JWT minting required.

    The session value is read ONLY from the explicit ``X-Superset-Session``
    header — the credential a client/proxy must send deliberately. Returns None
    when the header is absent (e.g. stdio mode).
    """
    try:
        request = ctx.request_context.request
        if request is None:
            return None
        return request.headers.get("x-superset-session", "").strip() or None
    except (AttributeError, LookupError):
        return None


async def create_superset_context() -> SupersetContext:
    """Create a new SupersetContext with a shared HTTP client."""
    client = httpx.AsyncClient(base_url=config.base_url, timeout=30.0, follow_redirects=True)
    return SupersetContext(client=client, base_url=config.base_url)


async def close_superset_context(ctx: SupersetContext) -> None:
    """Close HTTP client and cleanup."""
    await ctx.client.aclose()


async def lifespan_manager(server: Any) -> AsyncIterator[SupersetContext]:
    """Manage Superset context lifecycle."""
    logger.info("Initializing Superset context...")
    ctx = await create_superset_context()
    try:
        yield ctx
    finally:
        logger.info("Shutting down Superset context...")
        await close_superset_context(ctx)
