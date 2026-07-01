"""
Superset authentication - exchange Azure AD token for Superset JWT.
"""

import logging
import os
import time

import httpx

log = logging.getLogger("auth-proxy")

SUPERSET_URL = os.environ.get("SUPERSET_URL", "http://superset:8088")
SUPERSET_ADMIN_USERNAME = os.environ.get("SUPERSET_ADMIN_USERNAME", "admin")
SUPERSET_ADMIN_PASSWORD = os.environ.get("SUPERSET_ADMIN_PASSWORD", "admin")

# Cache: { user_key: {"access_token": str, "expires_at": float} }
_superset_token_cache: dict = {}


async def get_superset_token(azure_access_token: str = None) -> tuple[str, str]:
    """
    Exchange an Azure AD access token for a Superset JWT.

    Superset must have AUTH_TYPE = AUTH_OAUTH configured. When it does,
    POST /api/v1/security/login with provider="oauth" and the Azure token
    causes Superset to verify the token with Azure, auto-create the user if
    needed, and return a Superset JWT for that user.

    Falls back to admin username/password if no Azure token is provided
    (e.g. for the superset-mcp service account).

    Returns (access_token, error_message).
    """
    if azure_access_token:
        return await _login_with_azure_token(azure_access_token)
    return await _login_with_admin_credentials()


async def _login_with_azure_token(azure_token: str) -> tuple[str, str]:
    """Exchange Azure AD token for Superset JWT via OAuth provider endpoint."""
    # Use a hash of the token as cache key so we don't store the raw token
    cache_key = f"azure_{hash(azure_token)}"

    cached = _superset_token_cache.get(cache_key)
    if cached and cached["expires_at"] > time.time() + 60:
        log.info("[superset] Using cached token for azure user")
        return cached["access_token"], None

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{SUPERSET_URL}/api/v1/security/login",
                json={
                    "provider": "oauth",
                    "access_token": azure_token,
                },
            )

        if resp.status_code == 200:
            data = resp.json()
            access_token = data.get("access_token")
            if access_token:
                _superset_token_cache[cache_key] = {
                    "access_token": access_token,
                    "expires_at": time.time() + 3600 * 4,  # match JWT_ACCESS_TOKEN_EXPIRES
                }
                log.info("[superset] Azure token exchange OK")
                return access_token, None
            return "", "No access_token in Superset response"

        # Superset not yet configured for OAuth — fall back to admin
        if resp.status_code in (400, 422):
            log.warning(
                "[superset] OAuth provider endpoint rejected token (status=%d) — "
                "Superset may not have AUTH_TYPE=AUTH_OAUTH configured yet. "
                "Falling back to admin credentials.",
                resp.status_code,
            )
            return await _login_with_admin_credentials()

        log.error("[superset] Azure token exchange failed: %d %s", resp.status_code, resp.text[:200])
        return "", f"Login failed: {resp.status_code}"

    except Exception as exc:
        log.error("[superset] Azure token exchange error: %s", exc)
        return "", f"Error: {exc}"


async def _login_with_admin_credentials() -> tuple[str, str]:
    """Login with local admin username/password. Used as fallback or for service account."""
    cache_key = "_admin_"
    cached = _superset_token_cache.get(cache_key)
    if cached and cached["expires_at"] > time.time() + 60:
        log.info("[superset] Using cached admin token")
        return cached["access_token"], None

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{SUPERSET_URL}/api/v1/security/login",
                json={
                    "username": SUPERSET_ADMIN_USERNAME,
                    "password": SUPERSET_ADMIN_PASSWORD,
                    "provider": "db",
                    "refresh": True,
                },
            )

        if resp.status_code == 200:
            data = resp.json()
            access_token = data.get("access_token")
            if access_token:
                _superset_token_cache[cache_key] = {
                    "access_token": access_token,
                    "expires_at": time.time() + 3600 * 4,
                }
                log.info("[superset] Admin login OK")
                return access_token, None
            return "", "No access_token in Superset response"

        log.error("[superset] Admin login failed: %d %s", resp.status_code, resp.text[:200])
        return "", f"Admin login failed: {resp.status_code}"

    except Exception as exc:
        log.error("[superset] Admin login error: %s", exc)
        return "", f"Error: {exc}"


def clear_superset_token_cache():
    global _superset_token_cache
    _superset_token_cache = {}
    log.info("[superset] Token cache cleared")
