from __future__ import annotations

import logging

import requests

from .config import Config

logger = logging.getLogger("minipay_support.api_client")


def api_healthcheck(cfg: Config) -> tuple[bool, str]:
    try:
        resp = requests.get(f"{cfg.api_base_url}/health", timeout=cfg.connect_timeout_seconds)
        if resp.status_code == 200:
            return True, "ok"
        return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
    except requests.exceptions.Timeout:
        return False, f"timed out after {cfg.connect_timeout_seconds}s"
    except requests.exceptions.RequestException as exc:
        return False, str(exc)
