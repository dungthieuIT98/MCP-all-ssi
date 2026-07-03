"""
MCP dispatcher — routes requests to trino_handlers or superset_handlers.
"""

import logging

from auth import token_state, token_valid, refresh_token, start_device_code_flow, login_message
from trino_handlers import (
    TRINO_TOOLS,
    UPSTREAM_URL,
    forward_to_upstream,
    handle_initialize,
    handle_notifications,
    handle_tools_list as _trino_handle_tools_list,
    handle_trino_tool_call,
)
from superset_handlers import SUPERSET_TOOLS, handle_get_superset_token


async def handle_tools_list(msg: dict, headers: dict) -> dict:
    data = await _trino_handle_tools_list(msg, headers)
    if "result" in data and "tools" in data["result"]:
        data["result"]["tools"] = data["result"]["tools"] + SUPERSET_TOOLS
    return data

log = logging.getLogger("auth-proxy")

FALLBACK_TOOLS = TRINO_TOOLS + SUPERSET_TOOLS

_SUPERSET_TOOL_NAMES = {t["name"] for t in SUPERSET_TOOLS}


def _login_required_response(msg: dict) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": msg.get("id"),
        "result": {
            "content": [{"type": "text", "text": login_message()}],
            "isError": False,
        },
    }


async def handle_tools_call(msg: dict, headers: dict) -> dict:
    tool_name = msg.get("params", {}).get("name", "<unknown>")

    log.info("─" * 60 + f" handle_tools_call  tool={tool_name}")
    log.info("[tool-call] id=%s  session=%s  tool=%s",
             msg.get("id"),
             headers.get("mcp-session-id") or token_state.get("upstream_session_id"),
             tool_name)

    if tool_name in _SUPERSET_TOOL_NAMES:
        return await handle_get_superset_token(msg)

    if not token_state["access_token"] or not token_valid():
        log.warning("[tool-call] no valid token — starting device code flow")
        if not token_state["polling"]:
            await start_device_code_flow()
        return _login_required_response(msg)

    if not token_valid():
        log.warning("[tool-call] token expired — attempting refresh")
        if not await refresh_token():
            return _login_required_response(msg)

    result = await handle_trino_tool_call(msg, headers)
    if result is not None:
        return result

    log.error("[tool-call] all attempts failed for tool=%s", tool_name)
    return {
        "jsonrpc": "2.0",
        "id": msg.get("id"),
        "result": {
            "content": [{"type": "text", "text": "Failed to acquire token. Check auth-proxy logs."}],
            "isError": True,
        },
    }
