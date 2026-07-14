"""Superset configuration — Azure AD (Microsoft Entra ID) OAuth login."""
import os

from flask_appbuilder.security.manager import AUTH_OAUTH

# ── Core ──────────────────────────────────────────────────────────────
# Signs sessions / CSRF tokens and encrypts stored DB passwords.
SECRET_KEY = os.environ["SUPERSET_SECRET_KEY"]

# ── Authentication: Azure AD OAuth ─────────────────────────────────────
AUTH_TYPE = AUTH_OAUTH

AZURE_TENANT_ID = os.environ["AZURE_TENANT_ID"]
AZURE_CLIENT_ID = os.environ["AZURE_CLIENT_ID"]
AZURE_CLIENT_SECRET = os.environ["AZURE_CLIENT_SECRET"]

OAUTH_PROVIDERS = [
    {
        "name": "azure",
        "icon": "fa-windows",
        "token_key": "access_token",
        "remote_app": {
            "client_id": AZURE_CLIENT_ID,
            "client_secret": AZURE_CLIENT_SECRET,
            "api_base_url": f"https://login.microsoftonline.com/{AZURE_TENANT_ID}/oauth2/v2.0/",
            "server_metadata_url": (
                f"https://login.microsoftonline.com/{AZURE_TENANT_ID}/v2.0/"
                ".well-known/openid-configuration"
            ),
            "client_kwargs": {
                "scope": "openid email profile User.Read",
                # Azure returns the id_token as a JWT; tell Authlib to verify it.
                "token_endpoint_auth_method": "client_secret_post",
            },
            "request_token_url": None,
        },
    }
]

# Auto-create a Superset user on first successful Azure login.
AUTH_USER_REGISTRATION = True
# Default role for auto-registered users. Use "Public"/"Gamma" for least
# privilege; "Admin" only while testing.
AUTH_USER_REGISTRATION_ROLE = "Gamma"

# Optional: map Azure AD groups/roles to Superset roles. Requires the
# "groups"/"roles" claim in the token (configure in the Azure app manifest).
# AUTH_ROLES_MAPPING = {
#     "<azure-group-object-id>": ["Admin"],
#     "<azure-group-object-id-2>": ["Gamma"],
# }
# AUTH_ROLES_SYNC_AT_LOGIN = True


class CustomSsoSecurityManager:
    """Placeholder — extend SupersetSecurityManager.oauth_user_info here if
    you need to parse claims from Azure differently (e.g. read the id_token)."""


# Superset >=2.1 already knows how to parse the Azure userinfo response, so no
# custom SECURITY_MANAGER is required for the standard flow above.

# ── Behind a reverse proxy / TLS termination ───────────────────────────
ENABLE_PROXY_FIX = True
