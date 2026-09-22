from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

import psycopg2
import psycopg2.extras

from .config import Config

logger = logging.getLogger("minipay_support.db")


@contextmanager
def cursor(cfg: Config) -> Iterator[object]:
    conn = psycopg2.connect(cfg.dsn())
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            yield cur
        finally:
            cur.close()
    finally:
        conn.close()


def db_healthcheck(cfg: Config) -> tuple[bool, str]:
    try:
        with cursor(cfg) as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return True, "ok"
    except Exception as exc:  # noqa: BLE001 - want to report any failure reason
        logger.warning("DB health check failed: %s", exc)
        return False, str(exc)
