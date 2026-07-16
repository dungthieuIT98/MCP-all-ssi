"""Authentication tools for Superset MCP."""
from __future__ import annotations

from typing import Any, Dict

from mcp.server.fastmcp import Context

from core.server import mcp
from core.context import get_caller_session, get_superset_context
from utils.decorators import handle_api_errors
from utils.constants import USER_ME


@mcp.tool()
@handle_api_errors
async def superset_auth_check_session_validity(ctx: Context) -> Dict[str, Any]:
    """Check whether the caller's forwarded session cookie is valid against Superset."""
    session = get_caller_session(ctx)
    if not session:
        return {"valid": False, "error": "No caller session in X-Superset-Session header"}

    superset_ctx = get_superset_context(ctx)
    try:
        response = await superset_ctx.client.get(
            USER_ME, headers={"Cookie": f"session={session}"}
        )
        if response.status_code == 200:
            return {"valid": True}
        return {"valid": False, "status_code": response.status_code, "error": response.text}
    except Exception as e:
        return {"valid": False, "error": str(e)}
