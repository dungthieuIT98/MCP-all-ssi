"""Superset MCP Server - Entry point."""
import logging

import uvicorn
from _mcp import mcp
import tools  # noqa: F401 — registers all @mcp.tool() decorators

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Starting Superset MCP server...")
    app = mcp.streamable_http_app()
    uvicorn.run(app, host="0.0.0.0", port=8000, forwarded_allow_ips="*")
