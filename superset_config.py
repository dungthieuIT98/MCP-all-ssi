import logging
import os
from datetime import timedelta
from flask_appbuilder.security.manager import AUTH_OAUTH

log = logging.getLogger("superset_config")

SECRET_KEY = os.environ.get("SUPERSET_SECRET_KEY", "supersetsecretkey-change-me")

TENANT_ID = os.environ.get("OAUTH_TENANT_ID", "0314c27a-7092-4151-8bbb-f71b64029748")
CLIENT_ID = os.environ.get("OAUTH_CLIENT_ID")

AUTH_TYPE = AUTH_OAUTH
AUTH_USER_REGISTRATION = True
AUTH_USER_REGISTRATION_ROLE = "Gamma"
AUTH_ROLES_SYNC_AT_LOGIN = True

OAUTH_PROVIDERS = [
    {
        "name": "azure",
        "icon": "fa-windows",
        "token_key": "access_token",
        "remote_app": {
            "client_id": os.environ.get("OAUTH_CLIENT_ID"),
            "client_secret": os.environ.get("OAUTH_CLIENT_SECRET"),
            "api_base_url": "https://graph.microsoft.com/v1.0/",
            "request_token_url": None,
            "access_token_url": f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token",
            "authorize_url": f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/authorize",
            "server_metadata_url": f"https://login.microsoftonline.com/{TENANT_ID}/v2.0/.well-known/openid-configuration",
            "client_kwargs": {"scope": "openid email profile"},
        },
    }
]

# Longer token lifetime so superset-mcp service account doesn't re-login often
JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=4)
JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)


# ── Azure AD token-exchange endpoint ──────────────────────────────────
# Superset's OAuth is browser-redirect only; there is no REST path to swap an
# Azure access token for a Superset JWT. This blueprint adds one:
#   POST /api/v1/security/azure_login  {"access_token": "<azure jwt>"}
# It verifies the Azure token against Azure's JWKS, auto-provisions the user
# (mirroring AUTH_USER_REGISTRATION_ROLE), and mints a per-user FAB JWT — the
# same create_access_token() call Superset's own /security/login uses. This is
# what carries the real user's identity (roles / RLS / audit) into Superset.

_AZURE_ISSUER = f"https://sts.windows.net/{TENANT_ID}/"
_AZURE_JWKS_URL = f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys"

# Cache the JWKS client at module scope so keys are fetched/rotated, not re-pulled per call.
_jwks_client = None


def _get_jwks_client():
    global _jwks_client
    if _jwks_client is None:
        import jwt
        _jwks_client = jwt.PyJWKClient(_AZURE_JWKS_URL)
    return _jwks_client


def _verify_azure_token(access_token: str) -> dict:
    """Verify an Azure AD access token and return its claims. Raises on failure."""
    import jwt

    signing_key = _get_jwks_client().get_signing_key_from_jwt(access_token)
    return jwt.decode(
        access_token,
        signing_key.key,
        algorithms=["RS256"],
        audience=CLIENT_ID,
        issuer=_AZURE_ISSUER,
    )


def _azure_login_view():
    """Flask view: exchange a verified Azure token for a per-user Superset JWT."""
    from flask import current_app, jsonify, request
    from flask_jwt_extended import create_access_token

    body = request.get_json(silent=True) or {}
    access_token = body.get("access_token")
    if not access_token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            access_token = auth[7:]
    if not access_token:
        return jsonify({"message": "Missing access_token"}), 400

    try:
        claims = _verify_azure_token(access_token)
    except Exception as exc:
        log.warning("[azure_login] token verification failed: %s", exc)
        return jsonify({"message": f"Invalid Azure token: {exc}"}), 401

    email = claims.get("email") or claims.get("upn") or claims.get("preferred_username")
    if not email:
        return jsonify({"message": "No email/upn claim in Azure token"}), 401

    sm = current_app.appbuilder.sm
    user = sm.find_user(email=email) or sm.find_user(username=email)
    if user is None:
        role = sm.find_role(sm.auth_user_registration_role)
        user = sm.add_user(
            username=email,
            first_name=claims.get("given_name", "") or email.split("@")[0],
            last_name=claims.get("family_name", "") or "",
            email=email,
            role=role,
        )
        if not user:
            return jsonify({"message": "Failed to provision user"}), 500
        log.info("[azure_login] provisioned new user=%s role=%s", email, sm.auth_user_registration_role)

    if not user.is_active:
        return jsonify({"message": "User is inactive"}), 403

    token = create_access_token(identity=str(user.id), fresh=True)
    log.info("[azure_login] issued JWT for user=%s id=%s", email, user.id)
    return jsonify({"access_token": token}), 200


def FLASK_APP_MUTATOR(app):
    app.add_url_rule(
        "/api/v1/security/azure_login",
        view_func=_azure_login_view,
        methods=["POST"],
    )
    # Exempt from CSRF: this is a token-exchange endpoint authenticated by the
    # Azure JWT in the body, not by a session cookie, so CSRF does not apply.
    csrf = app.extensions.get("csrf")
    if csrf is not None:
        csrf.exempt(_azure_login_view)
    log.info("[azure_login] registered POST /api/v1/security/azure_login (csrf-exempt)")
