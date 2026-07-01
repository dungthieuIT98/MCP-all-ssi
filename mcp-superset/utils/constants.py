"""API path constants for Superset endpoints."""

# Base paths
API_V1 = "/api/v1"

# Auth endpoints
AUTH_LOGIN = f"{API_V1}/security/login"
AUTH_REFRESH = f"{API_V1}/security/refresh"
AUTH_CSRF = f"{API_V1}/security/csrf_token"

# Dashboard endpoints
DASHBOARD_BASE = f"{API_V1}/dashboard"

# Chart endpoints
CHART_BASE = f"{API_V1}/chart"

# Database endpoints
DATABASE_BASE = f"{API_V1}/database"
DATABASE_TEST = f"{DATABASE_BASE}/test_connection"
DATABASE_VALIDATE_SQL = f"{DATABASE_BASE}/validate_sql"
DATABASE_VALIDATE_PARAMS = f"{DATABASE_BASE}/validate_parameters"

# Dataset endpoints
DATASET_BASE = f"{API_V1}/dataset"

# SQL Lab endpoints
SQLLAB_BASE = f"{API_V1}/sqllab"
SQLLAB_EXECUTE = f"{SQLLAB_BASE}/execute"
SQLLAB_FORMAT = f"{SQLLAB_BASE}/format_sql"
SQLLAB_RESULTS = f"{SQLLAB_BASE}/results"
SQLLAB_ESTIMATE = f"{SQLLAB_BASE}/estimate"
SQLLAB_EXPORT = f"{SQLLAB_BASE}/export"

# Saved query endpoints
SAVED_QUERY_BASE = f"{API_V1}/saved_query"

# Query endpoints
QUERY_BASE = f"{API_V1}/query"
QUERY_STOP = f"{QUERY_BASE}/stop"

# User endpoints
USER_ME = f"{API_V1}/me"
USER_ROLES = f"{USER_ME}/roles"

# Activity endpoints
ACTIVITY_RECENT = f"{API_V1}/log/recent_activity"

# Tag endpoints
TAG_BASE = f"{API_V1}/tag"
TAG_OBJECTS = f"{TAG_BASE}/tagged_objects"
TAG_GET_OBJECTS = f"{TAG_BASE}/get_objects"

# Explore endpoints
EXPLORE_FORM_DATA = f"{API_V1}/explore/form_data"
EXPLORE_PERMALINK = f"{API_V1}/explore/permalink"

# Menu endpoints
MENU = f"{API_V1}/menu"

# Advanced data type endpoints
ADVANCED_DATA_TYPE = f"{API_V1}/advanced_data_type"
