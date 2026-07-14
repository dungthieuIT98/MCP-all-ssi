"""Superset MCP - Model Context Protocol server for Apache Superset."""
from __future__ import annotations

import logging
from typing import Any

from _mcp import mcp
from client import SupersetContext, get_superset_context

# Import all tool modules to register tools with the MCP server
from tools import (
    auth,
    chart,
    dashboard,
    dataset,
    explore,
    tag,
    user,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

__all__ = ["mcp", "get_superset_context", "SupersetContext"]
