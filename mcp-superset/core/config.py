"""Configuration management for Superset MCP."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Load .env file
load_dotenv()


@dataclass
class Config:
    """Superset MCP configuration."""

    base_url: str


def get_config() -> Config:
    """Load configuration from environment variables."""
    return Config(
        base_url=os.getenv("SUPERSET_BASE_URL", "http://localhost:8088"),
    )
