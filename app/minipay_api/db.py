"""Database access layer for MiniPay API.

Uses plain psycopg2 (no ORM) so query behaviour is explicit and easy to
reason about during troubleshooting -- this mirrors how a small L2-owned
service is often built in the real world.
"""
from __future__ import annotations

import os
import logging
from contextlib import contextmanager
from typing import Any, Iterator

import psycopg2
import psycopg2.extras

logger = logging.getLogger("minipay.db")


def _dsn() -> str:
    # Configuration via environment variables only -- never hard-coded.
    host = os.environ.get("DB_HOST", "localhost")
    port = os.environ.get("DB_PORT", "5432")
    name = os.environ.get("DB_NAME", "minipay")
    user = os.environ.get("DB_USER", "minipay")
    password = os.environ.get("DB_PASSWORD", "minipay")
    return f"host={host} port={port} dbname={name} user={user} password={password} connect_timeout=3"


@contextmanager
def get_conn() -> Iterator[Any]:
    conn = psycopg2.connect(_dsn())
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_cursor(commit: bool = False) -> Iterator[Any]:
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            yield cur
            if commit:
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()


def healthcheck() -> bool:
    try:
        with get_cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return True
    except Exception as exc:  # pragma: no cover - exercised via /health tests
        logger.warning("DB health check failed: %s", exc)
        return False
