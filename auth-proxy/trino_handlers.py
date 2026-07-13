"""
Trino MCP handlers — forward requests to upstream trino-mcp.
Every handler is keyed by api_key: the Bearer token and upstream MCP session id
are looked up per-key from Postgres (see db.py).
"""

import json
import logging
import os

import httpx

import db
from auth import token_valid
from azure import refresh_token

log = logging.getLogger("auth-proxy")

UPSTREAM_URL = os.environ.get("UPSTREAM_URL", "http://host.docker.internal:6274/mcp")

SERVER_INFO = {
    "protocolVersion": "2024-11-05",
    "capabilities": {"tools": {"listChanged": False}},
    "serverInfo": {"name": "trino-auth-proxy", "version": "1.0.0"},
}

TRINO_TOOLS = [
    {"name": "execute_query", "description": "Execute SQL query on Trino", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "list_catalogs", "description": "List available Trino catalogs", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "list_schemas", "description": "List schemas in a catalog", "inputSchema": {"type": "object", "properties": {"catalog": {"type": "string"}}}},
    {"name": "list_tables", "description": "List tables in a schema", "inputSchema": {"type": "object", "properties": {"catalog": {"type": "string"}, "schema": {"type": "string"}}}},
    {"name": "get_table_schema", "description": "Get table column definitions", "inputSchema": {"type": "object", "properties": {"table": {"type": "string"}}, "required": ["table"]}},
    {"name": "explain_query", "description": "Explain query execution plan", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
]

# Static tool catalog fetched once from upstream — shared across users, not user data.
_cached_tools = None


def _sep(label: str = "") -> None:
    log.info("─" * 60 + (" " + label if label else ""))


async def _access_token(api_key: str) -> str | None:
    row = await db.get_by_api_key(api_key)
    return row.get("access_token") if row else None


async def _reinitialize(api_key: str) -> bool:
    """Get a fresh session ID from upstream for this api_key."""
    if await token_valid(api_key) != 1:
        if not await refresh_token(api_key):
            return False
    token = await _access_token(api_key)
    fwd_headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    body = json.dumps({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "trino-auth-proxy", "version": "1.0.0"},
    }}).encode()
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(UPSTREAM_URL, content=body, headers=fwd_headers)
    if resp.status_code == 200:
        session_id = resp.headers.get("mcp-session-id")
        if session_id:
            await db.set_upstream_session(api_key, session_id)
            log.info("[reinit] OK key=%s new session_id=%s", api_key, session_id)
            return True
    log.warning("[reinit] FAILED key=%s status=%s body=%s", api_key, resp.status_code, resp.text[:200])
    return False


async def forward_to_upstream(body: bytes, headers: dict, api_key: str) -> httpx.Response | None:
    if await token_valid(api_key) != 1:
        if not await refresh_token(api_key):
            log.error("[forward] key=%s token invalid and refresh failed — aborting", api_key)
            return None

    token = await _access_token(api_key)
    fwd_headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    if "mcp-session-id" in headers:
        fwd_headers["Mcp-Session-Id"] = headers["mcp-session-id"]
    else:
        row = await db.get_by_api_key(api_key)
        session_id = row.get("upstream_session_id") if row else None
        if session_id:
            fwd_headers["Mcp-Session-Id"] = session_id

    _sep("REQUEST → upstream")
    log.info("[forward] POST %s key=%s", UPSTREAM_URL, api_key)
    log.info("[forward] Mcp-Session-Id: %s", fwd_headers.get("Mcp-Session-Id", "<none>"))
    log.info("[forward] Authorization: Bearer %s...", (token or "")[:30])
    try:
        req_obj = json.loads(body)
        method = req_obj.get("method", "")
        params = req_obj.get("params", {})
        log.info("[forward] method=%s  id=%s", method, req_obj.get("id"))

        if method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            log.info("[forward] tool=%s", tool_name)
            if tool_name in ("execute_query", "explain_query"):
                sql = tool_args.get("query", "")
                log.info("[forward] ┌─ SQL (%d chars) ─────────────────────────", len(sql))
                for line in sql.splitlines():
                    log.info("[forward] │  %s", line)
                log.info("[forward] └──────────────────────────────────────────")
            else:
                log.info("[forward] args=%s", json.dumps(tool_args, ensure_ascii=False)[:300])
        else:
            log.info("[forward] params=%s", json.dumps(params, ensure_ascii=False)[:300])
    except Exception:
        log.info("[forward] body (raw): %s", body[:300])

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(UPSTREAM_URL, content=body, headers=fwd_headers)

    _sep("RESPONSE ← upstream")
    log.info("[forward] status=%d", resp.status_code)
    log.info("[forward] resp-headers: %s", dict(resp.headers))
    try:
        resp_obj = resp.json()
        if "error" in resp_obj:
            log.error("[forward] JSON-RPC error: %s", json.dumps(resp_obj["error"]))
        elif "result" in resp_obj:
            content = (resp_obj["result"] or {}).get("content") or []
            if content:
                for i, item in enumerate(content):
                    text = item.get("text", "")
                    log.info("[forward] result.content[%d] (%d chars): %s", i, len(text), text[:800])
            else:
                log.info("[forward] result (no content): %s", json.dumps(resp_obj["result"])[:500])
        else:
            log.info("[forward] raw resp: %s", resp.text[:500])
    except Exception:
        log.info("[forward] resp body (non-JSON): %s", resp.text[:500])
    _sep()

    if resp.status_code == 400 and "Invalid session" in resp.text:
        log.warning("[forward] key=%s invalid session — reinitializing and retrying", api_key)
        if await _reinitialize(api_key):
            row = await db.get_by_api_key(api_key)
            new_session = row.get("upstream_session_id") if row else None
            if new_session:
                fwd_headers["Mcp-Session-Id"] = new_session
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(UPSTREAM_URL, content=body, headers=fwd_headers)
            log.info("[forward] retry status=%d", resp.status_code)

    if resp.status_code == 401:
        log.warning("[forward] key=%s upstream 401 — token rejected: %s", api_key, resp.text[:300])
        return None

    return resp


async def handle_initialize(msg: dict, headers: dict, api_key: str) -> dict:
    _sep("handle_initialize")
    log.info("[init] client sent initialize  id=%s key=%s", msg.get("id"), api_key)

    if await token_valid(api_key) != 1:
        log.info("[init] key=%s token not valid, attempting refresh", api_key)
        await refresh_token(api_key)

    if await token_valid(api_key) == 1:
        body = json.dumps(msg).encode()
        resp = await forward_to_upstream(body, headers, api_key)
        if resp and resp.status_code == 200:
            try:
                result = resp.json()
                session_id = resp.headers.get("mcp-session-id")
                if session_id:
                    await db.set_upstream_session(api_key, session_id)
                    log.info("[init] key=%s upstream session_id=%s", api_key, session_id)
                log.info("[init] forwarded OK, returning upstream result")
                return result
            except Exception as exc:
                log.error("[init] JSON parse error: %s", exc)
    else:
        log.warning("[init] key=%s not authenticated — returning local SERVER_INFO", api_key)

    return {"jsonrpc": "2.0", "id": msg.get("id"), "result": SERVER_INFO}


async def handle_tools_list(msg: dict, headers: dict, api_key: str) -> dict:
    """Return the Trino tool list only — mcp_handlers merges SUPERSET_TOOLS on top."""
    global _cached_tools
    _sep("handle_tools_list")
    log.info("[tools/list] id=%s key=%s", msg.get("id"), api_key)

    if await token_valid(api_key) == 1:
        body = json.dumps(msg).encode()
        resp = await forward_to_upstream(body, headers, api_key)
        if resp and resp.status_code == 200:
            try:
                data = resp.json()
                if "result" in data and "tools" in data["result"]:
                    _cached_tools = data["result"]["tools"]
                    log.info("[tools/list] got %d tools from upstream", len(_cached_tools))
                return data
            except Exception as exc:
                log.error("[tools/list] JSON parse error: %s", exc)
        else:
            log.warning("[tools/list] upstream failed — falling back to cache/static")
    else:
        log.warning("[tools/list] key=%s not authenticated — using fallback tools", api_key)

    tools = _cached_tools or TRINO_TOOLS
    log.info("[tools/list] returning %d trino tools (fallback)", len(tools))
    return {"jsonrpc": "2.0", "id": msg.get("id"), "result": {"tools": tools}}


async def handle_trino_tool_call(msg: dict, headers: dict, api_key: str) -> dict:
    """Forward a Trino tool call to upstream. Assumes token check already done."""
    params = msg.get("params", {})
    tool_name = params.get("name", "<unknown>")
    tool_args = params.get("arguments", {})

    if tool_name in ("execute_query", "explain_query"):
        sql = tool_args.get("query", "")
        log.info("[tool-call] ┌─ SQL (%d chars) ───────────────────────────", len(sql))
        for line in sql.splitlines():
            log.info("[tool-call] │  %s", line)
        log.info("[tool-call] └──────────────────────────────────────────")
    else:
        log.info("[tool-call] args=%s", json.dumps(tool_args, ensure_ascii=False)[:400])

    body = json.dumps(msg).encode()
    resp = await forward_to_upstream(body, headers, api_key)
    if resp and resp.status_code == 200:
        try:
            data = resp.json()
            content_items = (data.get("result") or {}).get("content") or []
            log.info("[tool-call] ← %d content item(s)", len(content_items))
            for i, item in enumerate(content_items):
                text = item.get("text", "")
                log.info("[tool-call] ← content[%d] (%d chars): %s", i, len(text), text[:1000])
            if (data.get("result") or {}).get("isError"):
                log.warning("[tool-call] ← isError=True  full=%s", json.dumps(data)[:500])
            _sep()
            return data
        except Exception as exc:
            log.error("[tool-call] ← JSON parse error: %s  raw=%s", exc, resp.text[:300])
    elif resp is None and await _access_token(api_key):
        log.error("[tool-call] ← upstream returned None (401) for tool=%s key=%s", tool_name, api_key)
        return {
            "jsonrpc": "2.0",
            "id": msg.get("id"),
            "result": {
                "content": [{"type": "text", "text": "Token bi upstream reject (401). Kiem tra OIDC_AUDIENCE config cua trino-mcp."}],
                "isError": True,
            },
        }
    else:
        log.error("[tool-call] ← upstream error  status=%s  body=%s",
                  resp.status_code if resp else "None",
                  resp.text[:300] if resp else "")
    return None


async def handle_notifications(msg: dict, headers: dict, api_key: str):
    method = msg.get("method", "")
    log.info("[notify] method=%s key=%s", method, api_key)
    if await token_valid(api_key) == 1:
        body = json.dumps(msg).encode()
        await forward_to_upstream(body, headers, api_key)
    else:
        log.warning("[notify] key=%s skipped (not authenticated)", api_key)
