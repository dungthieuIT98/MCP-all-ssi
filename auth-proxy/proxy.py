"""
Auth Proxy for MCP Trino — sits between VS Code and trino-mcp (OAuth-protected).
Handles Azure AD Device Code Flow transparently, per api_key.

Callers are identified by the X-Api-Key header; its value is the api_key
(PRIMARY KEY of user_tokens — migration 004). Direct access to :6275 without
the header falls back to DEFAULT_API_KEY so local dev still works. Durable
tokens live in Postgres (see db.py), keyed by api_key.

Usage:
    python proxy.py
    # Then point .mcp.json to http://localhost:6275/mcp (or via Kong :8000)
"""

import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager

# psycopg async cannot run on Windows' default ProactorEventLoop — required
# for `python proxy.py` local dev on Windows; no-op in the Linux container.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

import db
from auth import token_valid
from azure import CLIENT_ID, CLIENT_SECRET, TENANT_ID
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
# IS the caller-supplied X-Api-Key header value (the api_key handed back
# on first device-code login) — no DB lookup needed: a key that has no row
# simply hasn't logged in yet and gets the device-code flow. Absent on direct
# :6275 access with no key → fall back to DEFAULT_API_KEY for local dev.
DEFAULT_API_KEY = os.environ.get(
    "DEFAULT_API_KEY", os.environ.get("DEFAULT_USERNAME", "_local")
)


def _resolve_api_key(headers: dict) -> str:
    """Caller identity = the X-Api-Key header value, verbatim."""
    api_key = headers.get("x-api-key")
    if not api_key:
        log.info(
            "[proxy] no X-Api-Key header — using fallback '%s'",
            DEFAULT_API_KEY,
        )
        return DEFAULT_API_KEY
    return api_key


async def mcp_endpoint(request: Request) -> Response:
    body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    api_key = _resolve_api_key(headers)

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
        "[proxy] → %s (id=%s) key=%s | token_valid=%s",
        method,
        msg_id,
        api_key,
        await token_valid(api_key),
    )

    if msg_id is None:
        log.info("[proxy] notification, fire-and-forget")
        await handle_notifications(msg, headers, api_key)
        return Response(status_code=202)

    if method == "initialize":
        result = await handle_initialize(msg, headers, api_key)
    elif method == "tools/list":
        result = await handle_tools_list(msg, headers, api_key)
    elif method == "tools/call":
        tool_name = msg.get("params", {}).get("name", "?")
        log.info("[proxy] tools/call name=%s key=%s", tool_name, api_key)
        result = await handle_tools_call(msg, headers, api_key)
    elif method == "ping":
        result = {"jsonrpc": "2.0", "id": msg_id, "result": {}}
    else:
        log.info("[proxy] unknown method=%s, forwarding", method)
        if await token_valid(api_key):
            resp = await forward_to_upstream(body, headers, api_key)
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

    log.info("[proxy] ← %s (id=%s) key=%s done", method, msg_id, api_key)
    resp_headers = {"Content-Type": "application/json"}
    session_id = await db.get_upstream_session(api_key)
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
    # uvicorn.run() hard-codes ProactorEventLoop on Windows, which psycopg
    # async cannot use — drive the server through asyncio.run() so the
    # SelectorEventLoop policy set above applies.
    config = uvicorn.Config(app, host="0.0.0.0", port=PROXY_PORT, log_level="info")
    asyncio.run(uvicorn.Server(config).serve())
