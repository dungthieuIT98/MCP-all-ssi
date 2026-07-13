"""Azure AD OAuth integration — device code flow and token management."""

import asyncio
import base64
import json
import logging
import os
import secrets
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

_device_state: dict[str, dict] = {}


def _device(api_key: str) -> dict:
	"""Get (or lazily create) the in-memory device-flow state for an api_key."""
	return _device_state.setdefault(
		api_key,
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
		payload += "=" * (4 - len(payload) % 4)
		decoded = base64.urlsafe_b64decode(payload)
		return json.loads(decoded)
	except Exception as e:
		log.warning("[auth.decode] Failed to decode token: %s", e)
		return {}


async def refresh_token(api_key: str) -> bool:
	"""Refresh the access token for this api_key using its stored refresh token."""
	row = await db.get_by_api_key(api_key)
	refresh = row.get("refresh_token") if row else None
	log.info("[auth.refresh] key=%s refresh_token present=%s", api_key, bool(refresh))
	if not refresh:
		return False

	try:
		async with httpx.AsyncClient() as client:
			data = {
				"client_id": CLIENT_ID,
				"grant_type": "refresh_token",
				"refresh_token": refresh,
				"scope": SCOPE,
			}
			log.info("[auth.refresh] POST %s grant=refresh_token key=%s", TOKEN_URL, api_key)
			resp = await client.post(TOKEN_URL, data=data)
	except httpx.HTTPError as exc:
		log.error("[auth.refresh] key=%s network error: %s", api_key, exc)
		return False

	log.info("[auth.refresh] key=%s status=%d", api_key, resp.status_code)
	if resp.status_code == 200:
		result = resp.json()
		claims = decode_token_payload(result["access_token"])
		await db.upsert_by_api_key(
			api_key,
			{
				"access_token": result["access_token"],
				"refresh_token": result.get("refresh_token", refresh),
				"expires_at": time.time() + result.get("expires_in", 3600),
				"token_claims": claims,
			},
		)
		log.info("[auth.refresh] OK key=%s upn=%s", api_key, _claims_upn(claims))
		return True

	log.warning("[auth.refresh] FAILED key=%s: %s", api_key, resp.text[:300])
	error = resp.json().get("error", "") if resp.headers.get("content-type", "").startswith("application/json") else ""
	if error in ("invalid_grant", "interaction_required"):
		await db.clear_tokens(api_key)
		log.warning("[auth.refresh] tokens cleared for key=%s due to: %s", api_key, error)
	return False


async def start_device_code_flow(api_key: str | None = None) -> tuple[bool, str]:
	"""Initiate device code flow. If api_key is not provided, a new one is created.
	Returns (success, api_key)."""
	if api_key is None:
		api_key = secrets.token_urlsafe(32)

	dev = _device(api_key)
	if dev["polling"]:
		log.info("[auth.device_code] key=%s already polling, reusing existing flow", api_key)
		return True, api_key

	log.info("[auth.device_code] Starting device code flow key=%s", api_key)

	try:
		async with httpx.AsyncClient() as client:
			data = {"client_id": CLIENT_ID, "scope": SCOPE}
			if CLIENT_SECRET:
				data["client_secret"] = CLIENT_SECRET
			resp = await client.post(DEVICE_CODE_URL, data=data)
	except httpx.HTTPError as exc:
		log.error("[auth.device_code] key=%s network error: %s", api_key, exc)
		return False, api_key

	log.info("[auth.device_code] key=%s status=%d", api_key, resp.status_code)
	if resp.status_code == 200:
		result = resp.json()
		device_code = result.get("device_code")
		user_code = result.get("user_code")
		verification_uri = result.get("verification_uri")
		expires_in = result.get("expires_in", 600)

		dev["device_code"] = device_code
		dev["user_code"] = user_code
		dev["verification_uri"] = verification_uri
		dev["polling"] = True
		dev["poll_task"] = asyncio.create_task(_poll_for_token(api_key, result.get("interval", 5)))

		# Save device code flow state (device code + verification info) to database
		await db.save_device_flow_state(
			api_key,
			device_code,
			user_code,
			verification_uri,
			time.time() + expires_in,
		)

		log.info("[auth.device_code] OK key=%s user_code=%s uri=%s interval=%s",
				 api_key, user_code, verification_uri, result.get("interval"))
		return True, api_key

	log.error("[auth.device_code] FAILED key=%s: %s", api_key, resp.text[:300])
	return False, api_key or ""


async def _poll_for_token(api_key: str, interval: int):
	"""Background task: poll Azure AD until the user authorizes, then store the
	resulting tokens in Postgres under this api_key."""
	dev = _device(api_key)
	log.info("[auth.poll] key=%s starting poll loop, interval=%d", api_key, interval)
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
				log.info("[auth.poll] key=%s #%d status=%d", api_key, poll_count, resp.status_code)

				if resp.status_code == 200:
					claims = decode_token_payload(data["access_token"])
					await db.upsert_by_api_key(
						api_key,
						{
							"access_token": data["access_token"],
							"refresh_token": data.get("refresh_token"),
							"expires_at": time.time() + data.get("expires_in", 3600),
							"token_claims": claims,
						},
					)
					dev["polling"] = False
					log.info("[auth.poll] OK key=%s login successful upn=%s",
							  api_key, _claims_upn(claims))
					return

				error = data.get("error", "")
				if error == "authorization_pending":
					continue
				elif error == "slow_down":
					interval += 5
					log.info("[auth.poll] key=%s slow_down, new interval=%d", api_key, interval)
				elif error in ("expired_token", "bad_verification_code"):
					log.warning("[auth.poll] key=%s device code expired", api_key)
					dev["polling"] = False
					dev["device_code"] = None
					return
				else:
					log.error("[auth.poll] key=%s unexpected error: %s", api_key, data)
					dev["polling"] = False
					return
	except Exception as e:
		log.error("[auth.poll] key=%s exception: %s", api_key, e, exc_info=True)
		dev["polling"] = False


def _claims_upn(claims: dict | None) -> str:
	c = claims or {}
	return c.get("upn") or c.get("preferred_username") or c.get("email") or c.get("unique_name", "?")
