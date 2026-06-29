"""
Auth Proxy for MCP Trino — sits between VS Code and trino-mcp (OAuth-protected).
Handles Azure AD Device Code Flow transparently.

Usage:
    python proxy.py
    # Then point .mcp.json to http://localhost:6275/mcp
"""

import json
import logging
import os

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from auth import token_state, token_valid, CLIENT_SECRET, CLIENT_ID, TENANT_ID
from mcp_handlers import (
    UPSTREAM_URL,
    forward_to_upstream,
    handle_initialize,
    handle_tools_list,
    handle_tools_call,
    handle_notifications,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("auth-proxy")

PROXY_PORT = int(os.environ.get("PROXY_PORT", 6275))


async def mcp_endpoint(request: Request) -> Response:
    body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}

    try:
        msg = json.loads(body)
    except json.JSONDecodeError:
        log.error("[proxy] JSON parse error")
        return JSONResponse({"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}}, status_code=400)

    method = msg.get("method", "")
    msg_id = msg.get("id")

    log.info("[proxy] → %s (id=%s) | token_valid=%s", method, msg_id, token_valid())

    if msg_id is None:
        log.info("[proxy] notification, fire-and-forget")
        await handle_notifications(msg, headers)
        return Response(status_code=202)

    if method == "initialize":
        result = await handle_initialize(msg, headers)
    elif method == "tools/list":
        result = await handle_tools_list(msg, headers)
    elif method == "tools/call":
        tool_name = msg.get("params", {}).get("name", "?")
        log.info("[proxy] tools/call name=%s", tool_name)
        result = await handle_tools_call(msg, headers)
    elif method == "ping":
        result = {"jsonrpc": "2.0", "id": msg_id, "result": {}}
    else:
        log.info("[proxy] unknown method=%s, forwarding", method)
        if token_valid():
            resp = await forward_to_upstream(body, headers)
            if resp and resp.status_code == 200:
                return Response(content=resp.content, status_code=200,
                                headers={"Content-Type": "application/json"})
        result = {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}

    log.info("[proxy] ← %s (id=%s) done", method, msg_id)
    resp_headers = {"Content-Type": "application/json"}
    if token_state.get("upstream_session_id"):
        resp_headers["Mcp-Session-Id"] = token_state["upstream_session_id"]
    return Response(content=json.dumps(result), status_code=200, headers=resp_headers)


app = Starlette(
    routes=[
        Route("/mcp", mcp_endpoint, methods=["POST"]),
        Route("/", lambda r: JSONResponse({
            "status": "ok",
            "authenticated": token_valid(),
            "polling": token_state.get("polling", False),
            "server": "trino-auth-proxy",
        })),
    ],
    middleware=[
        Middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"]),
    ],
)

if __name__ == "__main__":
    print(f"Auth Proxy starting on http://localhost:{PROXY_PORT}")
    print(f"  Upstream:  {UPSTREAM_URL}")
    print(f"  Tenant ID: {TENANT_ID}")
    print(f"  Client ID: {CLIENT_ID}")
    print(f"  Secret:    {'set' if CLIENT_SECRET else 'NOT SET'}")
    print()
    uvicorn.run(app, host="0.0.0.0", port=PROXY_PORT, log_level="info")
