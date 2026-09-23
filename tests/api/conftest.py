import os
import uuid

import psycopg2
import psycopg2.extras
import pytest
import requests

BASE_URL = os.environ.get("MINIPAY_API_URL", "http://localhost:8080")
API_KEY = os.environ.get("MINIPAY_API_KEY", "dev-local-key")


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture
def session():
    s = requests.Session()
    s.headers.update({"X-API-Key": API_KEY, "Content-Type": "application/json"})
    return s


@pytest.fixture
def anon_session():
    """A session with no API key, for auth-negative tests."""
    return requests.Session()


@pytest.fixture
def unique_customer_ref():
    return f"CUST-TEST-{uuid.uuid4().hex[:10]}"


@pytest.fixture
def unique_txn_ref():
    return f"TXN-TEST-{uuid.uuid4().hex[:10]}"


@pytest.fixture
def db_conn():
    conn = psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=os.environ.get("DB_PORT", "5432"),
        dbname=os.environ.get("DB_NAME", "minipay"),
        user=os.environ.get("DB_USER", "minipay"),
        password=os.environ.get("DB_PASSWORD", "minipay"),
        cursor_factory=psycopg2.extras.RealDictCursor,
    )
    yield conn
    conn.close()


@pytest.fixture
def created_customer(session, base_url, unique_customer_ref):
    resp = session.post(f"{base_url}/api/customers", json={"customer_ref": unique_customer_ref, "name": "Test User"})
    assert resp.status_code == 201, resp.text
    return resp.json()
