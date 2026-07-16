"""Superset client and context management."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import httpx
from mcp.server.fastmcp import Context

from core.config import get_config

config = get_config()


@dataclass
class SupersetContext:
    """Context for the Superset MCP server.

    Holds only the shared HTTP client and base URL. There is no service-account
    credential here by design: every request carries the caller's own Superset
    session cookie (see get_caller_session), so the server never authenticates
    as a shared account.
    """

    client: httpx.AsyncClient
    base_url: str
    csrf_token: Optional[str] = None


def get_superset_context(ctx: Context) -> SupersetContext:
    """Get SupersetContext from MCP Context."""
    return ctx.request_context.lifespan_context


def get_caller_session(ctx: Context) -> Optional[str]:
    """Extract the caller's Superset session cookie from the incoming request.

    Superset issues a Flask ``session`` cookie after any successful web login —
    including Azure AD / OAuth. Superset's own REST API accepts that session
    cookie (plus a CSRF token for writes), so forwarding it lets the
    authenticated user drive the API with their real identity and RLS. This is
    the ONLY credential the server uses — no JWT/Bearer token, no service account.

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
