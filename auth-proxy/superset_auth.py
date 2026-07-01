"""
Superset authentication - login and token management.
"""

import logging
import os
import time
from typing import Optional

import httpx

log = logging.getLogger("auth-proxy")

# Superset configuration
SUPERSET_URL = os.environ.get("SUPERSET_URL", "http://localhost:8088")
SUPERSET_ADMIN_USERNAME = os.environ.get("SUPERSET_ADMIN_USERNAME", "admin")
SUPERSET_ADMIN_PASSWORD = os.environ.get("SUPERSET_ADMIN_PASSWORD", "admin")

# Cache for Superset tokens per user
_superset_token_cache = {}


async def get_superset_token(user_email: str = None) -> tuple[str, str]:
    """
    Login to Superset and get access token.

    Args:
        user_email: The user's email/username to login as.
                   If None, uses admin credentials directly.

    Returns:
        (access_token, error_message)
    """
    global _superset_token_cache

    cache_key = user_email or "_admin_"

    # Check cache first
    if cache_key in _superset_token_cache:
        cached = _superset_token_cache[cache_key]
        if cached["expires_at"] > time.time() + 60:  # 60s leeway
            log.info(f"[superset] Using cached token for {cache_key}")
            return cached["access_token"], None

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Try to login as the user
            login_data = {
                "username": user_email or SUPERSET_ADMIN_USERNAME,
                "password": SUPERSET_ADMIN_PASSWORD,
                "provider": "db",
                "refresh": True,
            }
            log.info(f"[superset] Logging in as: {login_data['username']}")
            resp = await client.post(
                f"{SUPERSET_URL}/api/v1/security/login",
                json=login_data,
            )

            if resp.status_code == 200:
                data = resp.json()
                access_token = data.get("access_token")
                if access_token:
                    _superset_token_cache[cache_key] = {
                        "access_token": access_token,
                        "expires_at": time.time() + 3600,  # Superset tokens typically last
                    }
                    log.info(f"[superset] ✓ Logged in as {cache_key}")
                    return access_token, None
            elif resp.status_code == 401:
                # User doesn't exist with local password
                # Try admin login and return admin token (workaround)
                log.warning(f"[superset] User {cache_key} cannot login locally, using admin token")
                if cache_key != "_admin_":
                    admin_resp = await client.post(
                        f"{SUPERSET_URL}/api/v1/security/login",
                        json={
                            "username": SUPERSET_ADMIN_USERNAME,
                            "password": SUPERSET_ADMIN_PASSWORD,
                            "provider": "db",
                            "refresh": True,
                        },
                    )
                    if admin_resp.status_code == 200:
                        admin_data = admin_resp.json()
                        admin_token = admin_data.get("access_token")
                        if admin_token:
                            _superset_token_cache["_admin_"] = {
                                "access_token": admin_token,
                                "expires_at": time.time() + 3600,
                            }
                            # Return admin token with warning
                            return admin_token, f"Admin token returned (user {user_email} not found in Superset)"
                return "", f"Login failed for {user_email}: invalid credentials"
            else:
                error_text = resp.text[:200]
                log.error(f"[superset] Login failed: {resp.status_code} - {error_text}")
                return "", f"Login failed: {resp.status_code}"

    except Exception as e:
        log.error(f"[superset] Error: {e}")
        return "", f"Error: {e}"


def clear_superset_token_cache():
    """Clear the Superset token cache."""
    global _superset_token_cache
    _superset_token_cache = {}
    log.info("[superset] Token cache cleared")
