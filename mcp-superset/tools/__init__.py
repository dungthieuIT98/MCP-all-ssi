"""MCP tools for Superset."""
from tools import (
    auth,
    chart,
    dashboard,
    # database,     # hidden: disabled — query via Trino MCP instead
    dataset,
    explore,
    # query,        # hidden: not needed
    # saved_query,  # hidden: not needed
    # sqllab,       # hidden: disabled — query via Trino MCP instead
    # system,       # hidden: not needed
    tag,
    user,
)

__all__ = [
    "auth",
    "chart",
    "dashboard",
    "dataset",
    "explore",
    "tag",
    "user",
]
