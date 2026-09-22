"""MiniPay API - a small payment-processing service used for the
Paysys Labs Implementation/L2 assessment.

Endpoints:
  POST /api/customers
  POST /api/payments
  GET  /api/payments/{id}
  GET  /api/payments/search?ref=...
  GET  /api/customers/{id}/payments
  GET  /health

NOTE ON A KNOWN DEFECT (see investigation/INCIDENT-001-RCA.md):
  /api/payments/search intentionally assumes a transaction_ref is unique
  and will raise an unhandled exception (-> 500) when it is not. The
  seed data generator creates a small number of duplicate transaction_ref
  values on purpose. This is the reproduction case for INCIDENT-001 and
  is fixed in a later commit -- see git history / RCA doc.
"""
from __future__ import annotations

import logging
import os
import random
import string
import time
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from . import db
from .auth import require_api_key
from .models import CustomerCreate, CustomerOut, PaymentCreate, PaymentOut

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("minipay.api")

app = FastAPI(title="MiniPay API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start) * 1000
    logger.info(
        "%s %s -> %s (%.1fms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


def _gen_ref() -> str:
    suffix = "".join(random.choices(string.digits, k=8))
    return f"TXN{suffix}"


@app.get("/health")
def health():
    ok = db.healthcheck()
    if not ok:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="database unavailable")
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


@app.post("/api/customers", response_model=CustomerOut, status_code=status.HTTP_201_CREATED)
def create_customer(payload: CustomerCreate, _=Depends(require_api_key)):
    with db.get_cursor(commit=True) as cur:
        cur.execute("SELECT id FROM customers WHERE customer_ref = %s", (payload.customer_ref,))
        if cur.fetchone():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="customer_ref already exists")
        cur.execute(
            "INSERT INTO customers (customer_ref, name) VALUES (%s, %s) "
            "RETURNING id, customer_ref, name, created_at",
            (payload.customer_ref, payload.name),
        )
        row = cur.fetchone()
    return row


@app.post("/api/payments", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
def create_payment(payload: PaymentCreate, _=Depends(require_api_key)):
    with db.get_cursor(commit=True) as cur:
        cur.execute("SELECT id FROM customers WHERE customer_ref = %s", (payload.customer_ref,))
        customer = cur.fetchone()
        if not customer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="customer not found")

        transaction_ref = payload.transaction_ref or _gen_ref()

        # Idempotency: replaying a POST with a transaction_ref that already
        # exists must not create a second transaction.
        cur.execute(
            "SELECT id, transaction_ref, customer_id, amount, status, created_at, completed_at, failure_code "
            "FROM transactions WHERE transaction_ref = %s",
            (transaction_ref,),
        )
        existing = cur.fetchone()
        if existing:
            existing["idempotent_replay"] = True
            return existing

        now = datetime.utcnow()
        # Simplified synchronous settlement rule for a demo payment
        # processor: small amounts settle immediately, larger ones stay
        # PROCESSING to simulate awaiting an upstream callback. Documented
        # as a simplification in ARCHITECTURE.md.
        if payload.amount < 5000:
            new_status = "SUCCESS"
            completed_at = now
            failure_code = None
        else:
            new_status = "PROCESSING"
            completed_at = None
            failure_code = None

        cur.execute(
            "INSERT INTO transactions (transaction_ref, customer_id, amount, status, created_at, completed_at, failure_code) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "RETURNING id, transaction_ref, customer_id, amount, status, created_at, completed_at, failure_code",
            (transaction_ref, customer["id"], payload.amount, new_status, now, completed_at, failure_code),
        )
        row = cur.fetchone()
        row["idempotent_replay"] = False
    return row


@app.get("/api/payments/search", response_model=PaymentOut)
def search_payment(ref: str = Query(..., min_length=1), _=Depends(require_api_key)):
    """Search a transaction by its reference.

    KNOWN DEFECT (INCIDENT-001): transaction_ref has no uniqueness
    constraint at the database level, and this handler assumes exactly one
    row is returned. `(result,) = rows` raises ValueError for any ref that
    has more than one row, which FastAPI turns into an unhandled 500. This
    is the reproduction path documented in investigation/INCIDENT-001-RCA.md.
    Do not "fix" this by catching the exception here without reading that
    doc -- the fix is demonstrated as part of the incident, not silently
    patched in the main branch history.
    """
    with db.get_cursor() as cur:
        cur.execute(
            "SELECT id, transaction_ref, customer_id, amount, status, created_at, completed_at, failure_code "
            "FROM transactions WHERE transaction_ref = %s",
            (ref,),
        )
        rows = cur.fetchall()
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="transaction not found")
    (row,) = rows  # <-- intentional defect: fails when duplicates exist
    row["idempotent_replay"] = False
    return row


@app.get("/api/payments/{payment_id}", response_model=PaymentOut)
def get_payment(payment_id: int, _=Depends(require_api_key)):
    # NOTE: this route is declared *after* /api/payments/search on purpose.
    # FastAPI/Starlette match path routes in declaration order, and a
    # {payment_id} path parameter would otherwise greedily match the
    # literal "search" segment as payment_id="search", returning a 422
    # instead of ever reaching the search handler. Declare literal/static
    # paths before parameterised ones with a shared prefix.
    with db.get_cursor() as cur:
        cur.execute(
            "SELECT id, transaction_ref, customer_id, amount, status, created_at, completed_at, failure_code "
            "FROM transactions WHERE id = %s",
            (payment_id,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="transaction not found")
    row["idempotent_replay"] = False
    return row


@app.get("/api/customers/{customer_id}/payments", response_model=list[PaymentOut])
def list_customer_payments(customer_id: int, _=Depends(require_api_key)):
    with db.get_cursor() as cur:
        cur.execute("SELECT id FROM customers WHERE id = %s", (customer_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="customer not found")
        cur.execute(
            "SELECT id, transaction_ref, customer_id, amount, status, created_at, completed_at, failure_code "
            "FROM transactions WHERE customer_id = %s ORDER BY created_at DESC",
            (customer_id,),
        )
        rows = cur.fetchall()
    for r in rows:
        r["idempotent_replay"] = False
    return rows


# --- Minimal static UI (see requirements/06-ui-automation.md) -------------
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    def ui_index():
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))
