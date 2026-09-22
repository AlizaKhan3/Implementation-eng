"""Configuration for the support tool.

Precedence (highest wins): CLI flags > environment variables > defaults.
Never hard-code credentials -- see requirements/04-python-support-tool.md.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Config:
    db_host: str = os.environ.get("DB_HOST", "localhost")
    db_port: str = os.environ.get("DB_PORT", "5432")
    db_name: str = os.environ.get("DB_NAME", "minipay")
    db_user: str = os.environ.get("DB_USER", "minipay")
    db_password: str = os.environ.get("DB_PASSWORD", "minipay")
    api_base_url: str = os.environ.get("MINIPAY_API_URL", "http://localhost:8080")
    api_key: str = os.environ.get("MINIPAY_API_KEY", "dev-local-key")
    connect_timeout_seconds: float = float(os.environ.get("MINIPAY_TIMEOUT", "5"))
    stuck_threshold_minutes: int = int(os.environ.get("MINIPAY_STUCK_MINUTES", "15"))

    def dsn(self) -> str:
        return (
            f"host={self.db_host} port={self.db_port} dbname={self.db_name} "
            f"user={self.db_user} password={self.db_password} "
            f"connect_timeout={int(self.connect_timeout_seconds)}"
        )
