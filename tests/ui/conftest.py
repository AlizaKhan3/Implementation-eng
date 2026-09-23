import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("MINIPAY_UI_URL", "http://localhost:8080")
API_KEY = os.environ.get("MINIPAY_API_KEY", "dev-local-key")


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session")
def seeded_transaction():
    """Create a real customer + payment via the API so UI tests search for
    something that is guaranteed to exist, instead of depending on
    whatever happens to be in the seeded dataset."""
    customer_ref = f"CUST-UI-{uuid.uuid4().hex[:8]}"
    txn_ref = f"TXN-UI-{uuid.uuid4().hex[:8]}"
    headers = {"X-API-Key": API_KEY}

    requests.post(
        f"{BASE_URL}/api/customers", json={"customer_ref": customer_ref, "name": "UI Test Customer"}, headers=headers
    ).raise_for_status()
    requests.post(
        f"{BASE_URL}/api/payments",
        json={"customer_ref": customer_ref, "amount": "12.50", "transaction_ref": txn_ref},
        headers=headers,
    ).raise_for_status()

    return {"customer_ref": customer_ref, "transaction_ref": txn_ref}
