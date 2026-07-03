"""
Superset MCP handlers — forward read-only tool calls to mcp-superset,
and get Superset JWT for the authenticated Azure AD user.
"""

import json
import logging
import os

import httpx

from auth import token_state, token_valid, refresh_token, start_device_code_flow, login_message
from superset_auth import get_superset_token

log = logging.getLogger("auth-proxy")

SUPERSET_MCP_URL = os.environ.get("SUPERSET_MCP_URL", "http://host.docker.internal:6276/mcp")

# Read-only tools forwarded to mcp-superset (no create/update/delete)
SUPERSET_TOOLS = [
    # Auth
    {
        "name": "get_superset_token",
        "description": "Get Superset access token using Azure AD authentication",
        "inputSchema": {
            "type": "object",
            "properties": {
                "username": {
                    "type": "string",
                    "description": "Superset username (email). If not provided, uses admin credentials.",
                }
            },
        },
    },
    # Dashboard
    {
        "name": "superset_dashboard_list",
        "description": "List dashboards in Superset",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "superset_dashboard_get_by_id",
        "description": "Get details for a specific dashboard",
        "inputSchema": {
            "type": "object",
            "properties": {"dashboard_id": {"type": "integer"}},
            "required": ["dashboard_id"],
        },
    },
    # Chart
    {
        "name": "superset_chart_list",
        "description": "List charts in Superset",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "superset_chart_get_by_id",
        "description": "Get details for a specific chart",
        "inputSchema": {
            "type": "object",
            "properties": {"chart_id": {"type": "integer"}},
            "required": ["chart_id"],
        },
    },
    # Dataset
    {
        "name": "superset_dataset_list",
        "description": "List datasets in Superset",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "superset_dataset_get_by_id",
        "description": "Get details for a specific dataset",
        "inputSchema": {
            "type": "object",
            "properties": {"dataset_id": {"type": "integer"}},
            "required": ["dataset_id"],
        },
    },
    # Saved Query
    {
        "name": "superset_saved_query_get_by_id",
        "description": "Get details for a specific saved query",
        "inputSchema": {
            "type": "object",
            "properties": {"query_id": {"type": "integer"}},
            "required": ["query_id"],
        },
    },
    # Query
    {
        "name": "superset_query_list",
        "description": "List recent queries in Superset",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "superset_query_get_by_id",
        "description": "Get details for a specific query",
        "inputSchema": {
            "type": "object",
            "properties": {"query_id": {"type": "integer"}},
            "required": ["query_id"],
        },
    },
    # User / System
    {
        "name": "superset_user_get_current",
        "description": "Get information about the currently authenticated Superset user",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "superset_user_get_roles",
        "description": "Get roles for the current Superset user",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "superset_menu_get",
        "description": "Get the Superset menu/navigation data",
        "inputSchema": {"type": "object", "properties": {}},
    },
    # Tag
    {
        "name": "superset_tag_list",
        "description": "List tags in Superset",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "superset_tag_get_by_id",
        "description": "Get details for a specific tag",
        "inputSchema": {
            "type": "object",
            "properties": {"tag_id": {"type": "integer"}},
            "required": ["tag_id"],
        },
    },
    {
        "name": "superset_tag_objects",
        "description": "Get objects associated with tags",
        "inputSchema": {"type": "object", "properties": {}},
    },
]

_SUPERSET_FORWARD_TOOL_NAMES = {
    t["name"] for t in SUPERSET_TOOLS if t["name"] != "get_superset_token"
}

_superset_mcp_session_id: str | None = None


def _sep(label: str = "") -> None:
    log.info("─" * 60 + (" " + label if label else ""))


async def _get_superset_jwt() -> str | None:
    """Get a valid Superset JWT using admin service account credentials."""
    token, error = await get_superset_token(None)
    if error and not token:
        log.warning("[superset-forward] Failed to get Superset JWT: %s", error)
        return None
    return token


def _parse_sse_response(text: str, msg: dict) -> dict:
    """Extract the JSON payload from an SSE response body."""
    for line in text.splitlines():
        if line.startswith("data:"):
            data = line[5:].strip()
            try:
                return json.loads(data)
            except Exception:
                pass
    log.error("[superset-forward] could not parse SSE body: %s", text[:200])
    return {
        "jsonrpc": "2.0",
        "id": msg.get("id"),
        "result": {
            "content": [{"type": "text", "text": f"Unexpected SSE response: {text[:200]}"}],
            "isError": True,
        },
    }


async def _ensure_superset_session(jwt: str) -> bool:
    """Send initialize request to mcp-superset to establish a session."""
    global _superset_mcp_session_id

    if _superset_mcp_session_id:
        return True

    init_msg = {
        "jsonrpc": "2.0",
        "id": "init-1",
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "auth-proxy", "version": "1.0"},
        },
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": f"Bearer {jwt}",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(SUPERSET_MCP_URL, content=json.dumps(init_msg).encode(), headers=headers)
        session_id = resp.headers.get("mcp-session-id")
        if session_id:
            _superset_mcp_session_id = session_id
            log.info("[superset-session] initialized session_id=%s", session_id)
            return True
        log.warning("[superset-session] initialize returned no session id, status=%d", resp.status_code)
        return False
    except httpx.RequestError as exc:
        log.error("[superset-session] initialize failed: %s", exc)
        return False


async def _forward_to_superset_mcp(msg: dict) -> dict | None:
    """Forward a tool call to mcp-superset, injecting Superset JWT as auth."""
    global _superset_mcp_session_id

    superset_jwt = await _get_superset_jwt()
    if not superset_jwt:
        return {
            "jsonrpc": "2.0",
            "id": msg.get("id"),
            "result": {
                "content": [{"type": "text", "text": "Could not obtain Superset token. Check Superset connectivity."}],
                "isError": True,
            },
        }

    if not await _ensure_superset_session(superset_jwt):
        return {
            "jsonrpc": "2.0",
            "id": msg.get("id"),
            "result": {
                "content": [{"type": "text", "text": "Could not initialize mcp-superset session."}],
                "isError": True,
            },
        }

    fwd_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": f"Bearer {superset_jwt}",
    }
    if _superset_mcp_session_id:
        fwd_headers["Mcp-Session-Id"] = _superset_mcp_session_id

    body = json.dumps(msg).encode()

    _sep("REQUEST → mcp-superset")
    log.info("[superset-forward] POST %s  tool=%s",
             SUPERSET_MCP_URL, msg.get("params", {}).get("name", "?"))

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(SUPERSET_MCP_URL, content=body, headers=fwd_headers)
    except httpx.RequestError as exc:
        log.error("[superset-forward] Request error: %s", exc)
        return {
            "jsonrpc": "2.0",
            "id": msg.get("id"),
            "result": {
                "content": [{"type": "text", "text": f"Cannot reach mcp-superset at {SUPERSET_MCP_URL}: {exc}"}],
                "isError": True,
            },
        }

    log.info("[superset-forward] status=%d", resp.status_code)

    # Track session ID for subsequent calls
    new_session = resp.headers.get("mcp-session-id")
    if new_session:
        _superset_mcp_session_id = new_session

    if resp.status_code == 200:
        try:
            content_type = resp.headers.get("content-type", "")
            if "text/event-stream" in content_type:
                return _parse_sse_response(resp.text, msg)
            return resp.json()
        except Exception as exc:
            log.error("[superset-forward] parse error: %s", exc)

    # Session expired or missing — reset and retry once
    if resp.status_code == 400 and "session" in resp.text.lower():
        log.warning("[superset-forward] session invalid, resetting and retrying")
        _superset_mcp_session_id = None
        if await _ensure_superset_session(superset_jwt):
            fwd_headers["Mcp-Session-Id"] = _superset_mcp_session_id
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(SUPERSET_MCP_URL, content=body, headers=fwd_headers)
                if resp.status_code == 200:
                    content_type = resp.headers.get("content-type", "")
                    if "text/event-stream" in content_type:
                        return _parse_sse_response(resp.text, msg)
                    return resp.json()
            except httpx.RequestError as exc:
                log.error("[superset-forward] retry request error: %s", exc)

    log.error("[superset-forward] upstream error status=%d body=%s",
              resp.status_code, resp.text[:300])
    return {
        "jsonrpc": "2.0",
        "id": msg.get("id"),
        "result": {
            "content": [{"type": "text", "text": f"mcp-superset returned {resp.status_code}: {resp.text[:200]}"}],
            "isError": True,
        },
    }


async def handle_get_superset_token(msg: dict) -> dict:
    """Route Superset tool calls: get_superset_token handled locally, rest forwarded."""
    tool_name = msg.get("params", {}).get("name", "")

    # Forward read-only tools to mcp-superset
    if tool_name in _SUPERSET_FORWARD_TOOL_NAMES:
        if not token_valid():
            if not await refresh_token():
                if not token_state["polling"]:
                    await start_device_code_flow()
                return {
                    "jsonrpc": "2.0",
                    "id": msg.get("id"),
                    "result": {
                        "content": [{"type": "text", "text": login_message()}],
                        "isError": False,
                    },
                }
        return await _forward_to_superset_mcp(msg)

    # get_superset_token — handled locally
    _sep("handle_get_superset_token")

    if not token_valid():
        log.info("[superset-token] Azure AD token not valid, attempting refresh")
        if not await refresh_token():
            if not token_state["access_token"]:
                if not token_state["polling"]:
                    await start_device_code_flow()
                return {
                    "jsonrpc": "2.0",
                    "id": msg.get("id"),
                    "result": {
                        "content": [{"type": "text", "text": login_message()}],
                        "isError": False,
                    },
                }

    azure_token = token_state.get("access_token")
    user_email = None
    if token_state.get("token_claims"):
        claims = token_state["token_claims"]
        user_email = claims.get("upn") or claims.get("email") or claims.get("preferred_username")

    log.info("[superset-token] Exchanging Azure token for Superset JWT, user=%s", user_email)

    superset_token, error = await get_superset_token(azure_token)

    if error and not superset_token:
        return {
            "jsonrpc": "2.0",
            "id": msg.get("id"),
            "result": {
                "content": [{"type": "text", "text": f"Failed to get Superset token: {error}"}],
                "isError": True,
            },
        }

    result_data = {"superset_token": superset_token, "user": user_email}
    if error:
        result_data["warning"] = error

    return {
        "jsonrpc": "2.0",
        "id": msg.get("id"),
        "result": {
            "content": [{"type": "text", "text": json.dumps(result_data)}],
            "isError": False,
        },
    }
