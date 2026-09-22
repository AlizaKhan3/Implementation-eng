"""Core diagnostic logic for the support tool.

Deliberately DB-agnostic and API-agnostic in its analysis functions
(`analyze_transaction`) so they can be unit tested with plain dicts,
without a running database -- see python/tests/test_report.py.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


def fetch_transaction_records(cur: Any, ref: str) -> list[dict]:
    """Fetch every transaction row matching `ref`, each enriched with its
    callback attempts. Deliberately does NOT assume uniqueness -- this is
    the same transaction_ref column implicated in INCIDENT-001, and a
    support tool must surface duplicates rather than crash on them."""
    cur.execute(
        "SELECT id, transaction_ref, customer_id, amount, status, created_at, "
        "completed_at, failure_code FROM transactions WHERE transaction_ref = %s "
        "ORDER BY id",
        (ref,),
    )
    txns = cur.fetchall()
    for txn in txns:
        cur.execute(
            "SELECT attempt_no, http_status, callback_status, attempted_at "
            "FROM callbacks WHERE transaction_id = %s ORDER BY attempt_no",
            (txn["id"],),
        )
        txn["callbacks"] = cur.fetchall()
        cur.execute("SELECT customer_ref, name FROM customers WHERE id = %s", (txn["customer_id"],))
        cust = cur.fetchone()
        txn["customer_ref"] = cust["customer_ref"] if cust else None
        txn["customer_name"] = cust["name"] if cust else None
    return txns


def analyze_transaction(txn: dict, now: datetime, stuck_threshold_minutes: int) -> dict:
    """Given one transaction record (with a `callbacks` list attached),
    return detected anomalies and a recommended next action. Pure
    function -- no I/O -- so it is directly unit-testable."""
    anomalies: list[str] = []
    status = txn["status"]
    created_at = txn["created_at"]
    completed_at = txn.get("completed_at")
    failure_code = txn.get("failure_code")
    callbacks = txn.get("callbacks", [])

    if status == "PROCESSING":
        age = now - created_at
        if age > timedelta(minutes=stuck_threshold_minutes):
            anomalies.append(
                f"stuck in PROCESSING for {age} (threshold {stuck_threshold_minutes}m) "
                "-- likely never received a completion callback"
            )

    if status == "SUCCESS":
        if not any(cb["callback_status"] == "SUCCESS" for cb in callbacks):
            anomalies.append(
                "status is SUCCESS but no successful callback is recorded -- "
                "possible reconciliation gap between internal state and the "
                "upstream confirmation (see sql/06_reconciliation.sql)"
            )
        if completed_at is None:
            anomalies.append("status is SUCCESS but completed_at is NULL")

    if status == "FAILED" and not failure_code:
        anomalies.append("status is FAILED but failure_code is missing")

    failed_callbacks = [cb for cb in callbacks if cb["callback_status"] == "FAILED"]
    if len(failed_callbacks) >= 2:
        anomalies.append(
            f"{len(failed_callbacks)} failed callback attempts recorded -- "
            "possible upstream/webhook delivery issue"
        )

    if not anomalies:
        recommendation = "No anomaly detected. No action required."
    elif status == "PROCESSING":
        recommendation = (
            "Escalate to payments-platform on-call if age exceeds SLA; consider "
            "manually reconciling against the upstream processor before retrying."
        )
    elif status == "SUCCESS":
        recommendation = (
            "Verify with the upstream processor's own records before treating "
            "this as fully confirmed; do not blindly retry (risk of duplicate "
            "settlement)."
        )
    else:
        recommendation = "Review failure_code and callback history with the integration team."

    return {"anomalies": anomalies, "recommendation": recommendation}


def build_report(ref: str, txns: list[dict], now: datetime, stuck_threshold_minutes: int) -> dict:
    report: dict[str, Any] = {
        "queried_ref": ref,
        "generated_at": now.isoformat(),
        "match_count": len(txns),
        "matches": [],
    }
    if len(txns) > 1:
        report["duplicate_reference_warning"] = (
            f"{len(txns)} transactions share this reference. transaction_ref has "
            "no UNIQUE constraint at the DB level -- see "
            "investigation/INCIDENT-001-RCA.md. Do not assume ref uniquely "
            "identifies a transaction."
        )
    for txn in txns:
        analysis = analyze_transaction(txn, now, stuck_threshold_minutes)
        report["matches"].append(
            {
                "id": txn["id"],
                "transaction_ref": txn["transaction_ref"],
                "customer_ref": txn["customer_ref"],
                "customer_name": txn["customer_name"],
                "amount": str(txn["amount"]),
                "status": txn["status"],
                "created_at": txn["created_at"].isoformat(),
                "completed_at": txn["completed_at"].isoformat() if txn["completed_at"] else None,
                "failure_code": txn["failure_code"],
                "callbacks": [
                    {
                        "attempt_no": cb["attempt_no"],
                        "http_status": cb["http_status"],
                        "callback_status": cb["callback_status"],
                        "attempted_at": cb["attempted_at"].isoformat(),
                    }
                    for cb in txn["callbacks"]
                ],
                **analysis,
            }
        )
    return report


def fetch_stuck_transactions(cur: Any, stuck_threshold_minutes: int) -> list[dict]:
    cur.execute(
        "SELECT id, transaction_ref, customer_id, amount, created_at "
        "FROM transactions WHERE status = 'PROCESSING' "
        "AND created_at < now() - (%s || ' minutes')::interval "
        "ORDER BY created_at ASC",
        (stuck_threshold_minutes,),
    )
    return cur.fetchall()
