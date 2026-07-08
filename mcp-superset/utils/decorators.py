"""Decorators for Superset MCP tools."""
from __future__ import annotations

from functools import wraps
from typing import Any, Awaitable, Callable, Dict

from mcp.server.fastmcp import Context


def requires_auth(
    func: Callable[..., Awaitable[Dict[str, Any]]],
) -> Callable[..., Awaitable[Dict[str, Any]]]:
    """Decorator to check authentication before executing a function.

    Only accepts the caller's own forwarded token (per-user identity). The
    admin service-account token on SupersetContext is never treated as
    sufficient here, so a tool call can't pass this check without carrying
    the real user's identity through to Superset.
    """

    @wraps(func)
    async def wrapper(ctx: Context, *args, **kwargs) -> Dict[str, Any]:
        from client import get_caller_token

        if not get_caller_token(ctx):
            return {"error": "Not authenticated. Please authenticate first."}

        return await func(ctx, *args, **kwargs)

    return wrapper


def handle_api_errors(
    func: Callable[..., Awaitable[Dict[str, Any]]],
) -> Callable[..., Awaitable[Dict[str, Any]]]:
    """Decorator to handle API errors in a consistent way."""

    @wraps(func)
    async def wrapper(ctx: Context, *args, **kwargs) -> Dict[str, Any]:
        try:
            return await func(ctx, *args, **kwargs)
        except (TypeError, ValueError, KeyError) as e:
            # Catch programmer errors specifically for better debugging
            function_name = func.__name__
            return {"error": f"Error in {function_name}: {str(e)}"}
        except Exception as e:
            # Catch unexpected errors but include more context
            function_name = func.__name__
            return {"error": f"Unexpected error in {function_name}: {str(e)}"}

    return wrapper
