"""Shared FastMCP instance for Superset MCP server."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from core.context import (
    SupersetContext,
    close_superset_context,
    create_superset_context,
)


@asynccontextmanager
async def superset_lifespan(server: FastMCP) -> AsyncIterator[SupersetContext]:
    """Manage application lifecycle for Superset integration."""
    import logging

    logger = logging.getLogger(__name__)
    logger.info("Initializing Superset context...")
    ctx = await create_superset_context()
    try:
        yield ctx
    finally:
        logger.info("Shutting down Superset context...")
        await close_superset_context(ctx)


# Single shared MCP server instance
mcp = FastMCP(
    "superset",
    lifespan=superset_lifespan,
    dependencies=["fastapi", "uvicorn", "python-dotenv", "httpx"],
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)
