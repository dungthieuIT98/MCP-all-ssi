"""
Superset MCP handlers — forward read-only tool calls to mcp-superset,
and get Superset JWT for the authenticated Azure AD user.
"""

import json
import logging
import os

import httpx

import db
from auth import token_valid, refresh_token, start_device_code_flow, login_message
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

def _sep(label: str = "") -> None:
    log.info("─" * 60 + (" " + label if label else ""))


async def _get_superset_jwt(azure_token: str | None) -> str | None:
    """Get a valid per-user Superset JWT by exchanging the caller's Azure AD token."""
    token, error = await get_superset_token(azure_token)
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


async def _ensure_superset_session(username: str, jwt: str) -> str | None:
    """Ensure a per-user mcp-superset session exists; return the session id."""
    existing = await db.get_superset_session(username)
    if existing:
        return existing

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
            await db.set_superset_session(username, session_id)
            log.info("[superset-session] user=%s initialized session_id=%s", username, session_id)
            return session_id
        log.warning("[superset-session] user=%s initialize returned no session id, status=%d", username, resp.status_code)
        return None
    except httpx.RequestError as exc:
        log.error("[superset-session] user=%s initialize failed: %s", username, exc)
        return None


async def _forward_to_superset_mcp(msg: dict, username: str, azure_token: str | None) -> dict | None:
    """Forward a tool call to mcp-superset, injecting the per-user Superset JWT."""
    superset_jwt = await _get_superset_jwt(azure_token)
    if not superset_jwt:
        return {
            "jsonrpc": "2.0",
            "id": msg.get("id"),
            "result": {
                "content": [{"type": "text", "text": "Could not obtain Superset token. Check Superset connectivity."}],
                "isError": True,
            },
        }

    session_id = await _ensure_superset_session(username, superset_jwt)
    if not session_id:
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
        "Mcp-Session-Id": session_id,
    }

    body = json.dumps(msg).encode()

    _sep("REQUEST → mcp-superset")
    log.info("[superset-forward] POST %s  user=%s tool=%s",
             SUPERSET_MCP_URL, username, msg.get("params", {}).get("name", "?"))

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
    if new_session and new_session != session_id:
        await db.set_superset_session(username, new_session)

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
        log.warning("[superset-forward] user=%s session invalid, resetting and retrying", username)
        await db.set_superset_session(username, None)
        retry_session = await _ensure_superset_session(username, superset_jwt)
        if retry_session:
            fwd_headers["Mcp-Session-Id"] = retry_session
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


async def handle_get_superset_token(msg: dict, username: str) -> dict:
    """Route Superset tool calls: get_superset_token handled locally, rest forwarded."""
    tool_name = msg.get("params", {}).get("name", "")

    def _login_prompt():
        return {
            "jsonrpc": "2.0",
            "id": msg.get("id"),
            "result": {
                "content": [{"type": "text", "text": login_message(username)}],
                "isError": False,
            },
        }

    # Forward read-only tools to mcp-superset
    if tool_name in _SUPERSET_FORWARD_TOOL_NAMES:
        if not await token_valid(username):
            if not await refresh_token(username):
                await start_device_code_flow(username)
                return _login_prompt()
        row = await db.get_tokens(username)
        azure_token = row.get("access_token") if row else None
        return await _forward_to_superset_mcp(msg, username, azure_token)

    # get_superset_token — handled locally
    _sep("handle_get_superset_token")

    if not await token_valid(username):
        log.info("[superset-token] user=%s Azure AD token not valid, attempting refresh", username)
        if not await refresh_token(username):
            await start_device_code_flow(username)
            return _login_prompt()

    row = await db.get_tokens(username)
    azure_token = row.get("access_token") if row else None
    user_email = None
    claims = row.get("token_claims") if row else None
    if claims:
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
