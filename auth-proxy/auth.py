"""
Azure AD Device Code Flow — per-user token acquisition and refresh.

Durable tokens (access/refresh/expiry/claims) live in Postgres keyed by
username (see db.py). Device-flow transient state (device_code, user_code,
polling) is short-lived and process-local, so it stays in an in-memory dict
keyed by the same username. Nothing here is a global single-user token anymore.
"""

import asyncio
import base64
import json
import logging
import os
import time

import httpx

import db

log = logging.getLogger("auth-proxy")

TENANT_ID = os.environ["AZURE_TENANT_ID"]
CLIENT_ID = os.environ["AZURE_CLIENT_ID"]
SCOPE = f"{CLIENT_ID}/.default offline_access"
CLIENT_SECRET = os.environ.get("AZURE_CLIENT_SECRET", "")
DEVICE_CODE_URL = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/devicecode"
TOKEN_URL = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"

log.info("[auth] CLIENT_ID=%s CLIENT_SECRET_LEN=%d", CLIENT_ID, len(CLIENT_SECRET))

# Per-username transient device-flow state. NEVER persisted — the background
# poll task (and thus this state) dies with the process, and the values are
# meaningless across a restart. Durable tokens go to Postgres via db.py.
_device_state: dict[str, dict] = {}


def _device(username: str) -> dict:
    """Get (or lazily create) the in-memory device-flow state for a user."""
    return _device_state.setdefault(
        username,
        {
            "device_code": None,
            "user_code": None,
            "verification_uri": None,
            "polling": False,
            "poll_task": None,
        },
    )


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


def _claims_upn(claims: dict | None) -> str:
    c = claims or {}
    return c.get("upn") or c.get("preferred_username") or c.get("email") or c.get("unique_name", "?")


async def token_valid(username: str) -> bool:
    """True if the user has a non-expired access token in the DB."""
    row = await db.get_tokens(username)
    if not row or not row.get("access_token"):
        return False
    return time.time() < (row.get("expires_at") or 0) - 30


def login_message(username: str) -> str:
    dev = _device(username)
    uri = dev["verification_uri"] or "https://microsoft.com/devicelogin"
    code = dev["user_code"] or "..."
    return (
        f"Chua dang nhap Azure AD.\n\n"
        f"Truy cap: {uri}\n"
        f"Nhap code: {code}\n\n"
        f"Sau khi dang nhap xong, goi lai tool nay."
    )


async def refresh_token(username: str) -> bool:
    """Refresh the user's access token using their stored refresh token."""
    row = await db.get_tokens(username)
    refresh = row.get("refresh_token") if row else None
    log.info("[auth.refresh] user=%s refresh_token present=%s", username, bool(refresh))
    if not refresh:
        return False

    async with httpx.AsyncClient() as client:
        data = {
            "client_id": CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "scope": SCOPE,
        }
        log.info("[auth.refresh] POST %s grant=refresh_token user=%s", TOKEN_URL, username)
        resp = await client.post(TOKEN_URL, data=data)

    log.info("[auth.refresh] user=%s status=%d", username, resp.status_code)
    if resp.status_code == 200:
        result = resp.json()
        claims = decode_token_payload(result["access_token"])
        await db.upsert_tokens(
            username,
            access_token=result["access_token"],
            refresh_token=result.get("refresh_token", refresh),
            expires_at=time.time() + result.get("expires_in", 3600),
            token_claims=claims,
        )
        log.info("[auth.refresh] OK user=%s upn=%s", username, _claims_upn(claims))
        return True

    log.warning("[auth.refresh] FAILED user=%s: %s", username, resp.text[:300])
    # Only clear tokens if the refresh token is explicitly rejected.
    error = resp.json().get("error", "") if resp.headers.get("content-type", "").startswith("application/json") else ""
    if error in ("invalid_grant", "interaction_required"):
        await db.clear_tokens(username)
        log.warning("[auth.refresh] tokens cleared for user=%s due to: %s", username, error)
    return False


async def start_device_code_flow(username: str) -> bool:
    """Initiate device code flow for a user. Returns True if a device code was
    obtained (or a poll is already running for this user)."""
    dev = _device(username)
    # Self-guard: don't spawn a second poll loop if one is already running.
    # The handler-side check-then-call is not atomic across awaits.
    if dev["polling"]:
        log.info("[auth.device_code] user=%s already polling, reusing existing flow", username)
        return True

    log.info("[auth.device_code] Starting device code flow user=%s", username)
    async with httpx.AsyncClient() as client:
        data = {"client_id": CLIENT_ID, "scope": SCOPE}
        if CLIENT_SECRET:
            data["client_secret"] = CLIENT_SECRET
        resp = await client.post(DEVICE_CODE_URL, data=data)

    log.info("[auth.device_code] user=%s status=%d", username, resp.status_code)
    if resp.status_code == 200:
        result = resp.json()
        dev["device_code"] = result.get("device_code")
        dev["user_code"] = result.get("user_code")
        dev["verification_uri"] = result.get("verification_uri")
        dev["polling"] = True
        dev["poll_task"] = asyncio.create_task(_poll_for_token(username, result.get("interval", 5)))
        log.info("[auth.device_code] OK user=%s user_code=%s uri=%s interval=%s",
                 username, dev["user_code"], dev["verification_uri"], result.get("interval"))
        return True

    log.error("[auth.device_code] FAILED user=%s: %s", username, resp.text[:300])
    return False


async def _poll_for_token(username: str, interval: int):
    """Background task: poll Azure AD until the user authorizes, then store the
    resulting tokens in Postgres under their username."""
    dev = _device(username)
    log.info("[auth.poll] user=%s starting poll loop, interval=%d", username, interval)
    try:
        async with httpx.AsyncClient() as client:
            poll_count = 0
            while dev["polling"]:
                await asyncio.sleep(interval)
                poll_count += 1

                poll_data = {
                    "client_id": CLIENT_ID,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "device_code": dev["device_code"],
                }
                if CLIENT_SECRET:
                    poll_data["client_secret"] = CLIENT_SECRET

                resp = await client.post(TOKEN_URL, data=poll_data)
                data = resp.json()
                log.info("[auth.poll] user=%s #%d status=%d", username, poll_count, resp.status_code)

                if resp.status_code == 200:
                    claims = decode_token_payload(data["access_token"])
                    await db.upsert_tokens(
                        username,
                        access_token=data["access_token"],
                        refresh_token=data.get("refresh_token"),
                        expires_at=time.time() + data.get("expires_in", 3600),
                        token_claims=claims,
                    )
                    api_key = await db.ensure_api_key(username)
                    dev["polling"] = False
                    log.info("[auth.poll] OK user=%s login successful upn=%s api_key=%s...",
                              username, _claims_upn(claims), api_key[:8])
                    return

                error = data.get("error", "")
                if error == "authorization_pending":
                    continue
                elif error == "slow_down":
                    interval += 5
                    log.info("[auth.poll] user=%s slow_down, new interval=%d", username, interval)
                elif error in ("expired_token", "bad_verification_code"):
                    log.warning("[auth.poll] user=%s device code expired", username)
                    dev["polling"] = False
                    dev["device_code"] = None
                    return
                else:
                    log.error("[auth.poll] user=%s unexpected error: %s", username, data)
                    dev["polling"] = False
                    return
    except Exception as e:
        log.error("[auth.poll] user=%s exception: %s", username, e, exc_info=True)
        dev["polling"] = False
