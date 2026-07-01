import os
from datetime import timedelta
from flask_appbuilder.security.manager import AUTH_OAUTH

SECRET_KEY = os.environ.get("SUPERSET_SECRET_KEY", "supersetsecretkey-change-me")

TENANT_ID = os.environ.get("OAUTH_TENANT_ID", "0314c27a-7092-4151-8bbb-f71b64029748")

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
