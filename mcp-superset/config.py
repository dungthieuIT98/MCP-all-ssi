"""Configuration management for Superset MCP."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

# Load .env file
load_dotenv()


@dataclass
class Config:
    """Superset MCP configuration."""

    base_url: str
    username: Optional[str]
    password: Optional[str]
    token_store_path: str


def get_config() -> Config:
    """Load configuration from environment variables."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return Config(
        base_url=os.getenv("SUPERSET_BASE_URL", "http://localhost:8088"),
        username=os.getenv("SUPERSET_USERNAME"),
        password=os.getenv("SUPERSET_PASSWORD"),
        token_store_path=os.path.join(base_dir, ".superset_token"),
    )
