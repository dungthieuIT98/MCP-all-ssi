"""API path constants for Superset endpoints.

Only the endpoints used by the currently enabled (read-only) tools are kept
here. Constants for disabled tool groups (database, SQL Lab, query, saved
query, menu, advanced data type) and the old token-auth flow (login/refresh)
were removed — re-add them if those tools are re-enabled.
"""

# Base paths
API_V1 = "/api/v1"

# Auth endpoints
AUTH_CSRF = f"{API_V1}/security/csrf_token"

# Dashboard endpoints
DASHBOARD_BASE = f"{API_V1}/dashboard"

# Chart endpoints
CHART_BASE = f"{API_V1}/chart"

# Dataset endpoints
DATASET_BASE = f"{API_V1}/dataset"

# User endpoints
USER_ME = f"{API_V1}/me"
USER_ROLES = f"{USER_ME}/roles"

# Activity endpoints
ACTIVITY_RECENT = f"{API_V1}/log/recent_activity"

# Tag endpoints
TAG_BASE = f"{API_V1}/tag"
TAG_GET_OBJECTS = f"{TAG_BASE}/get_objects"

# Explore endpoints
EXPLORE_FORM_DATA = f"{API_V1}/explore/form_data"
EXPLORE_PERMALINK = f"{API_V1}/explore/permalink"
