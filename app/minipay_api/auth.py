"""Minimal API-key authentication.

Real MiniPay would sit behind proper OAuth2/mTLS; for this assessment a
single shared API key is a reasonable, honestly-documented simplification
(see ARCHITECTURE.md).
"""
import os
from fastapi import Header, HTTPException, status

API_KEY = os.environ.get("MINIPAY_API_KEY", "dev-local-key")


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or missing API key")
