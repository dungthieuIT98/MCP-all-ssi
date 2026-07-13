"""
MCP dispatcher — routes requests to trino_handlers or superset_handlers.
Every handler is keyed by api_key; identity comes from the X-Api-Key header
resolved in proxy.py.
"""

import logging

from auth import token_valid, login_message
from azure import refresh_token, start_device_code_flow
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

log = logging.getLogger("auth-proxy")

_SUPERSET_TOOL_NAMES = {t["name"] for t in SUPERSET_TOOLS}
_TRINO_TOOL_NAMES = {t["name"] for t in TRINO_TOOLS}


async def handle_tools_list(msg: dict, headers: dict, api_key: str) -> dict:
    data = await _trino_handle_tools_list(msg, headers, api_key)
    if "result" in data and "tools" in data["result"]:
        data["result"]["tools"] = data["result"]["tools"] + SUPERSET_TOOLS
    return data


def _login_required_response(msg: dict, api_key: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": msg.get("id"),
        "result": {
            "content": [{"type": "text", "text": login_message(api_key)}],
            "isError": False,
        },
    }


async def handle_tools_call(msg: dict, headers: dict, api_key: str) -> dict:
    tool_name = msg.get("params", {}).get("name", "<unknown>")

    log.info("─" * 60 + f" handle_tools_call  tool={tool_name}")
    log.info("[tool-call] id=%s  key=%s  tool=%s", msg.get("id"), api_key, tool_name)

    if await token_valid(api_key) != 1:
        log.warning("[tool-call] key=%s no valid token — attempting refresh", api_key)
        if not await refresh_token(api_key):
            log.warning(
                "[tool-call] key=%s refresh failed — starting device code flow",
                api_key,
            )
            ok, new_api_key = await start_device_code_flow(api_key)
            if not ok:
                return {
                    "jsonrpc": "2.0",
                    "id": msg.get("id"),
                    "result": {
                        "content": [{
                            "type": "text",
                            "text": "Khong the ket noi Azure AD de bat dau dang nhap. "
                                    "Kiem tra mang/cau hinh roi thu lai.",
                        }],
                        "isError": True,
                    },
                }
            return _login_required_response(msg, new_api_key)

    if tool_name in _SUPERSET_TOOL_NAMES:
        return await handle_get_superset_token(msg, api_key)

    if tool_name in _TRINO_TOOL_NAMES:
        return await handle_trino_tool_call(msg, headers, api_key)

    log.error(
        "[tool-call] all attempts failed for tool=%s key=%s", tool_name, api_key
    )
    return {
        "jsonrpc": "2.0",
        "id": msg.get("id"),
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": "Failed to acquire token. Check auth-proxy logs.",
                }
            ],
            "isError": True,
        },
    }
