"""Authentication tools for Superset MCP."""
from __future__ import annotations

from typing import Any, Dict

from mcp.server.fastmcp import Context

from _mcp import mcp
from client import get_caller_token, get_superset_context
from utils.decorators import handle_api_errors
from utils.constants import USER_ME


@mcp.tool()
@handle_api_errors
async def superset_auth_check_token_validity(ctx: Context) -> Dict[str, Any]:
    """Check whether the caller's forwarded token is valid against Superset."""
    caller_token = get_caller_token(ctx)
    if not caller_token:
        return {"valid": False, "error": "No caller token in Authorization header"}

    superset_ctx = get_superset_context(ctx)
    try:
        response = await superset_ctx.client.get(
            USER_ME, headers={"Authorization": f"Bearer {caller_token}"}
        )
        if response.status_code == 200:
            return {"valid": True}
        return {"valid": False, "status_code": response.status_code, "error": response.text}
    except Exception as e:
        return {"valid": False, "error": str(e)}
