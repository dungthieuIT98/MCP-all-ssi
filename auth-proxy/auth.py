"""
Azure AD Device Code Flow — token acquisition and refresh.
"""

import asyncio
import base64
import json
import logging
import os
import time

import httpx

log = logging.getLogger("auth-proxy")

TENANT_ID = "0314c27a-7092-4151-8bbb-f71b64029748"
CLIENT_ID = "dd72be28-a3ed-4d76-a601-ffff997c1e42"
SCOPE = "dd72be28-a3ed-4d76-a601-ffff997c1e42/.default offline_access"
CLIENT_SECRET = os.environ.get("CLIENT_SECRET", "")
DEVICE_CODE_URL = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/devicecode"
TOKEN_URL = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"

log.info("[auth] CLIENT_ID=%s CLIENT_SECRET_LEN=%d", CLIENT_ID, len(CLIENT_SECRET))

TOKEN_CACHE_PATH = "/app/cache/token_cache.json"

token_state = {
    "access_token": None,
    "refresh_token": None,
    "expires_at": 0,
    "device_code": None,
    "user_code": None,
    "verification_uri": None,
    "polling": False,
    "upstream_session_id": None,
    "token_claims": None,
}


def _save_token_cache():
    try:
        data = {
            "access_token": token_state["access_token"],
            "refresh_token": token_state["refresh_token"],
            "expires_at": token_state["expires_at"],
            "token_claims": token_state["token_claims"],
        }
        with open(TOKEN_CACHE_PATH, "w") as f:
            json.dump(data, f)
        log.info("[auth.cache] Saved token cache")
    except Exception as e:
        log.warning("[auth.cache] Failed to save: %s", e)


def _load_token_cache():
    try:
        if not os.path.exists(TOKEN_CACHE_PATH):
            return
        with open(TOKEN_CACHE_PATH) as f:
            data = json.load(f)
        token_state["access_token"] = data.get("access_token")
        token_state["refresh_token"] = data.get("refresh_token")
        token_state["expires_at"] = data.get("expires_at", 0)
        token_state["token_claims"] = data.get("token_claims")
        upn = (token_state["token_claims"] or {}).get("upn") or (token_state["token_claims"] or {}).get("preferred_username", "?")
        log.info("[auth.cache] Loaded token cache, user=%s expires_at=%.0f", upn, token_state["expires_at"])
    except Exception as e:
        log.warning("[auth.cache] Failed to load: %s", e)


_load_token_cache()


def decode_token_payload(token: str) -> dict:
    """Decode JWT payload (middle part) without verifying signature."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return {}
        payload = parts[1]
        # Re-add base64 padding
        payload += "=" * (4 - len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
    except Exception as e:
        log.warning("[auth.decode] Failed to decode token: %s", e)
        return {}


def token_valid() -> bool:
    valid = bool(token_state["access_token"]) and time.time() < token_state["expires_at"] - 30
    return valid


def login_message() -> str:
    uri = token_state["verification_uri"] or "https://microsoft.com/devicelogin"
    code = token_state["user_code"] or "..."
    return (
        f"Chua dang nhap Azure AD.\n\n"
        f"Truy cap: {uri}\n"
        f"Nhap code: {code}\n\n"
        f"Sau khi dang nhap xong, goi lai tool nay."
    )


async def refresh_token() -> bool:
    log.info("[auth.refresh] refresh_token present=%s", bool(token_state["refresh_token"]))
    if not token_state["refresh_token"]:
        return False
    async with httpx.AsyncClient() as client:
        data = {
            "client_id": CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": token_state["refresh_token"],
            "scope": SCOPE,
        }
        log.info("[auth.refresh] POST %s grant=refresh_token", TOKEN_URL)
        resp = await client.post(TOKEN_URL, data=data)
    log.info("[auth.refresh] status=%d", resp.status_code)
    if resp.status_code == 200:
        result = resp.json()
        token_state["access_token"] = result["access_token"]
        token_state["refresh_token"] = result.get("refresh_token", token_state["refresh_token"])
        token_state["expires_at"] = time.time() + result.get("expires_in", 3600)
        token_state["token_claims"] = decode_token_payload(result["access_token"])
        c = token_state["token_claims"]
        upn = c.get("upn") or c.get("preferred_username") or c.get("email") or c.get("unique_name", "?")
        _save_token_cache()
        log.info("[auth.refresh] ✓ Token refreshed, user=%s expires_at=%.0f", upn, token_state["expires_at"])
        return True
    log.warning("[auth.refresh] ✗ Failed: %s", resp.text[:300])
    # Only clear tokens if refresh_token is explicitly rejected
    error = resp.json().get("error", "") if resp.headers.get("content-type", "").startswith("application/json") else ""
    if error in ("invalid_grant", "interaction_required"):
        token_state["access_token"] = None
        token_state["refresh_token"] = None
        log.warning("[auth.refresh] Tokens cleared due to: %s", error)
    return False


async def start_device_code_flow() -> bool:
    """Initiate device code flow. Returns True if device code was obtained."""
    log.info("[auth.device_code] Starting device code flow")
    log.info("[auth.device_code] CLIENT_ID=%s SCOPE=%s CLIENT_SECRET_LEN=%d",
             CLIENT_ID, SCOPE, len(CLIENT_SECRET))
    async with httpx.AsyncClient() as client:
        data = {"client_id": CLIENT_ID, "scope": SCOPE}
        if CLIENT_SECRET:
            data["client_secret"] = CLIENT_SECRET
        log.info("[auth.device_code] POST %s data_keys=%s", DEVICE_CODE_URL, list(data.keys()))
        resp = await client.post(DEVICE_CODE_URL, data=data)

    log.info("[auth.device_code] status=%d", resp.status_code)
    if resp.status_code == 200:
        result = resp.json()
        token_state["device_code"] = result.get("device_code")
        token_state["user_code"] = result.get("user_code")
        token_state["verification_uri"] = result.get("verification_uri")
        token_state["polling"] = True
        asyncio.create_task(_poll_for_token(result.get("interval", 5)))
        log.info("[auth.device_code] ✓ user_code=%s verification_uri=%s interval=%s",
                 token_state["user_code"], token_state["verification_uri"], result.get("interval"))
        return True
    else:
        log.error("[auth.device_code] ✗ Failed: %s", resp.text[:300])
        return False


async def _poll_for_token(interval: int):
    """Background task: poll Azure AD until user authorizes."""
    log.info("[auth.poll] Starting poll loop, interval=%d", interval)
    try:
        async with httpx.AsyncClient() as client:
            poll_count = 0
            while token_state["polling"]:
                await asyncio.sleep(interval)
                poll_count += 1

                poll_data = {
                    "client_id": CLIENT_ID,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "device_code": token_state["device_code"],
                }
                if CLIENT_SECRET:
                    poll_data["client_secret"] = CLIENT_SECRET

                log.info("[auth.poll] #%d keys=%s client_secret_len=%d device_code_len=%d",
                         poll_count, list(poll_data.keys()),
                         len(poll_data.get("client_secret", "")),
                         len(poll_data.get("device_code", "")))

                resp = await client.post(TOKEN_URL, data=poll_data)
                log.info("[auth.poll] #%d status=%d", poll_count, resp.status_code)
                data = resp.json()
                log.info("[auth.poll] #%d body=%s", poll_count, str(data)[:300])

                if resp.status_code == 200:
                    token_state["access_token"] = data["access_token"]
                    token_state["refresh_token"] = data.get("refresh_token")
                    token_state["expires_at"] = time.time() + data.get("expires_in", 3600)
                    token_state["token_claims"] = decode_token_payload(data["access_token"])
                    token_state["polling"] = False
                    upn = token_state["token_claims"].get("upn") or token_state["token_claims"].get("preferred_username") or token_state["token_claims"].get("email") or token_state["token_claims"].get("unique_name", "?")
                    _save_token_cache()
                    log.info("[auth.poll] ✓ Login successful! user=%s access_token_len=%d expires_at=%.0f",
                             upn, len(token_state["access_token"]), token_state["expires_at"])
                    return

                error = data.get("error", "")
                if error == "authorization_pending":
                    log.debug("[auth.poll] #%d authorization_pending", poll_count)
                    continue
                elif error == "slow_down":
                    interval += 5
                    log.info("[auth.poll] slow_down, new interval=%d", interval)
                elif error in ("expired_token", "bad_verification_code"):
                    log.warning("[auth.poll] ✗ Device code expired")
                    token_state["polling"] = False
                    token_state["device_code"] = None
                    return
                else:
                    log.error("[auth.poll] ✗ Unexpected error: %s", data)
                    token_state["polling"] = False
                    return
    except Exception as e:
        log.error("[auth.poll] Exception: %s", e, exc_info=True)
        token_state["polling"] = False
