"""API test suite for MiniPay.

Run with:  cd tests/api && pytest -v
(requires the API + DB reachable per MINIPAY_API_URL / DB_* env vars --
see SETUP.md)
"""
import time

import pytest


# --- successful requests ---------------------------------------------------

def test_create_customer_success(session, base_url, unique_customer_ref):
    resp = session.post(f"{base_url}/api/customers", json={"customer_ref": unique_customer_ref, "name": "Alice"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["customer_ref"] == unique_customer_ref
    assert body["name"] == "Alice"
    assert isinstance(body["id"], int)
    assert "created_at" in body


def test_create_payment_success(session, base_url, created_customer, unique_txn_ref):
    resp = session.post(
        f"{base_url}/api/payments",
        json={"customer_ref": created_customer["customer_ref"], "amount": "10.00", "transaction_ref": unique_txn_ref},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["transaction_ref"] == unique_txn_ref
    assert body["status"] in ("SUCCESS", "PROCESSING")
    assert body["idempotent_replay"] is False


def test_get_payment_by_id(session, base_url, created_customer, unique_txn_ref):
    create = session.post(
        f"{base_url}/api/payments",
        json={"customer_ref": created_customer["customer_ref"], "amount": "10.00", "transaction_ref": unique_txn_ref},
    ).json()
    resp = session.get(f"{base_url}/api/payments/{create['id']}")
    assert resp.status_code == 200
    assert resp.json()["transaction_ref"] == unique_txn_ref


def test_list_customer_payments(session, base_url, created_customer, unique_txn_ref):
    session.post(
        f"{base_url}/api/payments",
        json={"customer_ref": created_customer["customer_ref"], "amount": "10.00", "transaction_ref": unique_txn_ref},
    )
    resp = session.get(f"{base_url}/api/customers/{created_customer['id']}/payments")
    assert resp.status_code == 200
    refs = [p["transaction_ref"] for p in resp.json()]
    assert unique_txn_ref in refs


# --- invalid / missing fields -----------------------------------------------

def test_create_customer_missing_name(session, base_url, unique_customer_ref):
    resp = session.post(f"{base_url}/api/customers", json={"customer_ref": unique_customer_ref})
    assert resp.status_code == 422


def test_create_payment_negative_amount(session, base_url, created_customer):
    resp = session.post(
        f"{base_url}/api/payments", json={"customer_ref": created_customer["customer_ref"], "amount": -5}
    )
    assert resp.status_code == 422


def test_create_payment_zero_amount(session, base_url, created_customer):
    resp = session.post(
        f"{base_url}/api/payments", json={"customer_ref": created_customer["customer_ref"], "amount": 0}
    )
    assert resp.status_code == 422


# --- unknown resources -------------------------------------------------------

def test_get_payment_unknown_id(session, base_url):
    resp = session.get(f"{base_url}/api/payments/99999999")
    assert resp.status_code == 404


def test_create_payment_unknown_customer(session, base_url, unique_txn_ref):
    resp = session.post(
        f"{base_url}/api/payments",
        json={"customer_ref": "CUST-DOES-NOT-EXIST", "amount": "10.00", "transaction_ref": unique_txn_ref},
    )
    assert resp.status_code == 404


def test_list_payments_unknown_customer(session, base_url):
    resp = session.get(f"{base_url}/api/customers/99999999/payments")
    assert resp.status_code == 404


def test_search_unknown_ref(session, base_url):
    resp = session.get(f"{base_url}/api/payments/search", params={"ref": "TXN-DOES-NOT-EXIST"})
    assert resp.status_code == 404


# --- auth / access control ---------------------------------------------------

def test_create_customer_no_api_key_rejected(anon_session, base_url, unique_customer_ref):
    resp = anon_session.post(f"{base_url}/api/customers", json={"customer_ref": unique_customer_ref, "name": "X"})
    assert resp.status_code == 401


def test_wrong_api_key_rejected(base_url, unique_customer_ref):
    import requests

    s = requests.Session()
    s.headers.update({"X-API-Key": "totally-wrong-key"})
    resp = s.post(f"{base_url}/api/customers", json={"customer_ref": unique_customer_ref, "name": "X"})
    assert resp.status_code == 401


def test_health_does_not_require_auth(anon_session, base_url):
    resp = anon_session.get(f"{base_url}/health")
    assert resp.status_code == 200


# --- duplicate / idempotent payment submission -------------------------------

def test_idempotent_payment_replay_returns_same_transaction(session, base_url, created_customer, unique_txn_ref):
    payload = {"customer_ref": created_customer["customer_ref"], "amount": "42.00", "transaction_ref": unique_txn_ref}
    first = session.post(f"{base_url}/api/payments", json=payload)
    assert first.status_code == 201
    first_body = first.json()
    assert first_body["idempotent_replay"] is False

    second = session.post(f"{base_url}/api/payments", json=payload)
    assert second.status_code == 200  # not 201 -- no new resource was created
    second_body = second.json()
    assert second_body["id"] == first_body["id"]
    assert second_body["idempotent_replay"] is True


# --- server error behaviour (INCIDENT-001 reproduction) ----------------------

def test_search_with_duplicate_ref_returns_500(session, base_url, db_conn, created_customer, unique_txn_ref):
    """Reproduces INCIDENT-001: transaction_ref has no DB-level uniqueness
    constraint. Two rows sharing a ref make /api/payments/search crash.
    See investigation/INCIDENT-001-RCA.md -- this test documents the
    defect's existence; it is expected to fail once the permanent fix
    (making the column unique / making search duplicate-safe) ships, at
    which point this test should be updated to assert the new, safe
    behaviour instead of xfailing it away."""
    cur = db_conn.cursor()
    cur.execute(
        "INSERT INTO transactions (transaction_ref, customer_id, amount, status, created_at) "
        "VALUES (%s, %s, 1.00, 'SUCCESS', now())",
        (unique_txn_ref, created_customer["id"]),
    )
    cur.execute(
        "INSERT INTO transactions (transaction_ref, customer_id, amount, status, created_at) "
        "VALUES (%s, %s, 2.00, 'SUCCESS', now())",
        (unique_txn_ref, created_customer["id"]),
    )
    db_conn.commit()

    resp = session.get(f"{base_url}/api/payments/search", params={"ref": unique_txn_ref})
    assert resp.status_code == 500


# --- response schema / content assertions ------------------------------------

def test_payment_response_schema(session, base_url, created_customer, unique_txn_ref):
    resp = session.post(
        f"{base_url}/api/payments",
        json={"customer_ref": created_customer["customer_ref"], "amount": "5.50", "transaction_ref": unique_txn_ref},
    )
    body = resp.json()
    expected_keys = {
        "id", "transaction_ref", "customer_id", "amount", "status",
        "created_at", "completed_at", "failure_code", "idempotent_replay",
    }
    assert expected_keys.issubset(body.keys())
    assert isinstance(body["id"], int)
    assert body["status"] in ("PROCESSING", "SUCCESS", "FAILED")
    assert resp.headers["content-type"].startswith("application/json")


# --- response-time assertion --------------------------------------------------

def test_health_response_time_under_threshold(session, base_url):
    start = time.perf_counter()
    resp = session.get(f"{base_url}/health")
    elapsed = time.perf_counter() - start
    assert resp.status_code == 200
    assert elapsed < 1.0, f"/health took {elapsed:.3f}s, expected < 1.0s"
