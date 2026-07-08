"""
MCP dispatcher — routes requests to trino_handlers or superset_handlers.
Every handler is username-aware; identity comes from the X-Consumer-Username
header resolved in proxy.py.
"""

import logging

from auth import token_valid, refresh_token, start_device_code_flow
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


async def handle_tools_list(msg: dict, headers: dict, username: str) -> dict:
    data = await _trino_handle_tools_list(msg, headers, username)
    if "result" in data and "tools" in data["result"]:
        data["result"]["tools"] = data["result"]["tools"] + SUPERSET_TOOLS
    return data

log = logging.getLogger("auth-proxy")

FALLBACK_TOOLS = TRINO_TOOLS + SUPERSET_TOOLS

_SUPERSET_TOOL_NAMES = {t["name"] for t in SUPERSET_TOOLS}


async def _login_required_response(msg: dict, username: str) -> dict:
    """Return login message with device code + API key info."""
    from auth import get_login_response

    login_info = await get_login_response(username)
    text = (
        f"Chưa đăng nhập Azure AD.\n\n"
        f"Truy cập: {login_info['verification_uri']}\n"
        f"Nhập code: {login_info['user_code']}\n"
        f"API Key: {login_info['api_key']}\n\n"
        f"Sau khi đăng nhập xong, gọi lại tool này."
    )
    return {
        "jsonrpc": "2.0",
        "id": msg.get("id"),
        "result": {
            "content": [{"type": "text", "text": text}],
            "isError": False,
        },
    }


async def handle_tools_call(msg: dict, headers: dict, username: str) -> dict:
    tool_name = msg.get("params", {}).get("name", "<unknown>")

    log.info("─" * 60 + f" handle_tools_call  tool={tool_name}")
    log.info("[tool-call] id=%s  user=%s  tool=%s", msg.get("id"), username, tool_name)

    if tool_name in _SUPERSET_TOOL_NAMES:
        return await handle_get_superset_token(msg, username)

    if not await token_valid(username):
        log.warning("[tool-call] user=%s no valid token — attempting refresh", username)
        if not await refresh_token(username):
            log.warning("[tool-call] user=%s refresh failed — starting device code flow", username)
            await start_device_code_flow(username)
            return await _login_required_response(msg, username)

    result = await handle_trino_tool_call(msg, headers, username)
    if result is not None:
        return result

    log.error("[tool-call] all attempts failed for tool=%s user=%s", tool_name, username)
    return {
        "jsonrpc": "2.0",
        "id": msg.get("id"),
        "result": {
            "content": [{"type": "text", "text": "Failed to acquire token. Check auth-proxy logs."}],
            "isError": True,
        },
    }
