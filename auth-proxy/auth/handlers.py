"""Auth handlers — login messages, token validation, keyed by api_key (X-Api-Key)."""

import logging
import time

import db
from azure.oauth import (
    _device,
    start_device_code_flow as _start_device_code_flow,
    refresh_token,
)

log = logging.getLogger("auth-proxy")


async def token_valid(api_key: str | None) -> int:
    """0 = api_key not in DB (never logged in), 1 = valid non-expired token, 2 = found but expired."""
    row = await db.get_by_api_key(api_key)
    if not row or not row.get("access_token"):
        return 0
    if time.time() < (row.get("expires_at") or 0) - 30:
        return 1
    return 2


def login_message(api_key: str) -> str:
    """Login instructions: verification URL, user code, and the API key to send
    as X-Api-Key on subsequent calls."""
    dev = _device(api_key)
    uri = dev["verification_uri"] or "https://microsoft.com/devicelogin"
    code = dev["user_code"] or "..."
    return (
        f"Chua dang nhap Azure AD.\n\n"
        f"Truy cap: {uri}\n"
        f"Nhap code: {code}\n"
        f"API Key (X-Api-Key): {api_key}\n\n"
        f"Sau khi dang nhap xong, goi lai tool nay."
    )
