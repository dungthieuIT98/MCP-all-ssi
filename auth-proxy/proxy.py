"""
Auth Proxy for MCP Trino — sits between VS Code and trino-mcp (OAuth-protected).
Handles Azure AD Device Code Flow transparently, per user.

Users are identified by the X-Consumer-Username header Kong injects. Direct
access to :6275 (bypassing Kong) falls back to DEFAULT_USERNAME so local dev
still works. Durable tokens live in Postgres (see db.py), keyed by username.

Usage:
    python proxy.py
    # Then point .mcp.json to http://localhost:6275/mcp (or via Kong :8000)
"""

import json
import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

import db
from auth import token_valid, CLIENT_SECRET, CLIENT_ID, TENANT_ID
from mcp_handlers import (
    UPSTREAM_URL,
    forward_to_upstream,
    handle_initialize,
    handle_tools_list,
    handle_tools_call,
    handle_notifications,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("auth-proxy")

PROXY_PORT = int(os.environ.get("PROXY_PORT", 6275))
# Kong is a bare reverse proxy here — no auth plugin, no consumers. Identity
# comes from the caller-supplied X-Profile-Key header (the api_key handed
# back on first successful device-code login), resolved against Postgres.
# Absent on direct :6275 access with no key → fall back to DEFAULT_USERNAME
# for local dev.
DEFAULT_USERNAME = os.environ.get("DEFAULT_USERNAME", "_local")


async def _resolve_username(headers: dict) -> str | None:
    """Resolve caller identity from X-Profile-Key. Returns None if a key was
    supplied but doesn't match any user (invalid key — caller must be rejected,
    not silently downgraded to DEFAULT_USERNAME)."""
    api_key = headers.get("x-profile-key")
    if not api_key:
        log.info(
            "[proxy] no X-Profile-Key header — using fallback '%s'",
            DEFAULT_USERNAME,
        )
        return DEFAULT_USERNAME

    username = await db.get_username_by_api_key(api_key)
    if not username:
        log.warning("[proxy] X-Profile-Key did not match any user")
        return None
    return username


async def mcp_endpoint(request: Request) -> Response:
    body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    username = await _resolve_username(headers)

    if username is None:
        log.warning("[proxy] rejecting request — invalid X-Profile-Key")
        return JSONResponse(
            {"jsonrpc": "2.0", "error": {"code": -32000, "message": "Invalid X-Profile-Key"}},
            status_code=401,
        )

    try:
        msg = json.loads(body)
    except json.JSONDecodeError:
        log.error("[proxy] JSON parse error")
        return JSONResponse(
            {"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}},
            status_code=400,
        )

    method = msg.get("method", "")
    msg_id = msg.get("id")

    log.info(
        "[proxy] → %s (id=%s) user=%s | token_valid=%s",
        method,
        msg_id,
        username,
        await token_valid(username),
    )

    if msg_id is None:
        log.info("[proxy] notification, fire-and-forget")
        await handle_notifications(msg, headers, username)
        return Response(status_code=202)

    if method == "initialize":
        result = await handle_initialize(msg, headers, username)
    elif method == "tools/list":
        result = await handle_tools_list(msg, headers, username)
    elif method == "tools/call":
        tool_name = msg.get("params", {}).get("name", "?")
        log.info("[proxy] tools/call name=%s user=%s", tool_name, username)
        result = await handle_tools_call(msg, headers, username)
    elif method == "ping":
        result = {"jsonrpc": "2.0", "id": msg_id, "result": {}}
    else:
        log.info("[proxy] unknown method=%s, forwarding", method)
        if await token_valid(username):
            resp = await forward_to_upstream(body, headers, username)
            if resp and resp.status_code == 200:
                return Response(
                    content=resp.content,
                    status_code=200,
                    headers={"Content-Type": "application/json"},
                )
        result = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }

    log.info("[proxy] ← %s (id=%s) user=%s done", method, msg_id, username)
    resp_headers = {"Content-Type": "application/json"}
    session_id = await db.get_upstream_session(username)
    if session_id:
        resp_headers["Mcp-Session-Id"] = session_id
    return Response(content=json.dumps(result), status_code=200, headers=resp_headers)


@asynccontextmanager
async def lifespan(app):
    await db.init_pool()
    await db.run_migrations()
    log.info("[startup] DB pool ready, migrations applied")
    yield
    await db.close_pool()


app = Starlette(
    routes=[
        Route("/mcp", mcp_endpoint, methods=["POST"]),
        Route(
            "/",
            lambda r: JSONResponse(
                {
                    "status": "ok",
                    "server": "trino-auth-proxy",
                }
            ),
        ),
    ],
    middleware=[
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        ),
    ],
    lifespan=lifespan,
)

if __name__ == "__main__":
    print(f"Auth Proxy starting on http://localhost:{PROXY_PORT}")
    print(f"  Upstream:  {UPSTREAM_URL}")
    print(f"  Tenant ID: {TENANT_ID}")
    print(f"  Client ID: {CLIENT_ID}")
    print(f"  Secret:    {'set' if CLIENT_SECRET else 'NOT SET'}")
    print()
    uvicorn.run(app, host="0.0.0.0", port=PROXY_PORT, log_level="info")
