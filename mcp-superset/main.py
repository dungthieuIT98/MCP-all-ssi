"""Superset MCP Server - Entry point."""
import logging

from _mcp import mcp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Starting Superset MCP server...")
    mcp.run()
