"""
Superset authentication - exchange Azure AD token for Superset JWT.
"""

import logging
import os
import time

import httpx

log = logging.getLogger("auth-proxy")

SUPERSET_URL = os.environ.get("SUPERSET_URL", "http://superset:8088")

_TOKEN_TTL = 3600 * 4

_superset_token_cache: dict = {}


async def get_superset_token(azure_access_token: str) -> tuple[str, str]:

    if not azure_access_token:
        return "", "No Azure AD access token provided"
    return await _login_with_azure_token(azure_access_token)


def _cached_token(cache_key: str) -> str | None:
    cached = _superset_token_cache.get(cache_key)
    if cached and cached["expires_at"] > time.time() + 60:
        return cached["access_token"]
    return None


def _store_token(cache_key: str, access_token: str) -> None:
    _superset_token_cache[cache_key] = {
        "access_token": access_token,
        "expires_at": time.time() + _TOKEN_TTL,
    }


async def _login_with_azure_token(azure_token: str) -> tuple[str, str]:

    # Use a hash of the token as cache key so we don't store the raw token
    cache_key = f"azure_{hash(azure_token)}"

    cached = _cached_token(cache_key)
    if cached:
        log.info("[superset] Using cached token for azure user")
        return cached, None

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{SUPERSET_URL}/api/v1/security/azure_login",
                json={"access_token": azure_token},
            )

        if resp.status_code == 200:
            access_token = resp.json().get("access_token")
            if access_token:
                _store_token(cache_key, access_token)
                log.info("[superset] Azure token exchange OK")
                return access_token, None
            return "", "No access_token in Superset response"

        if resp.status_code == 404:
            log.error(
                "[superset] azure_login endpoint not found (404). "
                "Ensure superset_config.py defines FLASK_APP_MUTATOR with /api/v1/security/azure_login."
            )
            return "", "Superset azure_login endpoint missing (404)"

        log.error(
            "[superset] Azure token exchange failed: %d %s",
            resp.status_code,
            resp.text[:200],
        )
        return "", f"Azure login failed ({resp.status_code}): {resp.text[:200]}"

    except Exception as exc:
        log.error("[superset] Azure token exchange error: %s", exc)
        return "", f"Error: {exc}"


def clear_superset_token_cache():
    global _superset_token_cache
    _superset_token_cache = {}
    log.info("[superset] Token cache cleared")
