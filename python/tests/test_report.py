from datetime import datetime, timedelta

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from minipay_support.report import analyze_transaction, build_report  # noqa: E402


NOW = datetime(2026, 9, 22, 12, 0, 0)


def make_txn(**overrides):
    base = {
        "id": 1,
        "transaction_ref": "TXN00000001",
        "customer_id": 1,
        "customer_ref": "CUST000001",
        "customer_name": "Alice",
        "amount": "100.00",
        "status": "SUCCESS",
        "created_at": NOW - timedelta(minutes=1),
        "completed_at": NOW - timedelta(seconds=30),
        "failure_code": None,
        "callbacks": [
            {"attempt_no": 1, "http_status": 200, "callback_status": "SUCCESS", "attempted_at": NOW},
        ],
    }
    base.update(overrides)
    return base


def test_healthy_success_has_no_anomalies():
    txn = make_txn()
    result = analyze_transaction(txn, NOW, stuck_threshold_minutes=15)
    assert result["anomalies"] == []


def test_stuck_processing_detected():
    txn = make_txn(status="PROCESSING", completed_at=None, callbacks=[], created_at=NOW - timedelta(minutes=30))
    result = analyze_transaction(txn, NOW, stuck_threshold_minutes=15)
    assert any("stuck in PROCESSING" in a for a in result["anomalies"])


def test_processing_within_threshold_is_not_stuck():
    txn = make_txn(status="PROCESSING", completed_at=None, callbacks=[], created_at=NOW - timedelta(minutes=5))
    result = analyze_transaction(txn, NOW, stuck_threshold_minutes=15)
    assert result["anomalies"] == []


def test_success_without_callback_flagged():
    txn = make_txn(callbacks=[])
    result = analyze_transaction(txn, NOW, stuck_threshold_minutes=15)
    assert any("no successful callback" in a for a in result["anomalies"])


def test_success_with_failed_callback_only_flagged():
    txn = make_txn(callbacks=[{"attempt_no": 1, "http_status": 500, "callback_status": "FAILED", "attempted_at": NOW}])
    result = analyze_transaction(txn, NOW, stuck_threshold_minutes=15)
    assert any("no successful callback" in a for a in result["anomalies"])


def test_failed_without_failure_code_flagged():
    txn = make_txn(status="FAILED", completed_at=NOW, callbacks=[])
    result = analyze_transaction(txn, NOW, stuck_threshold_minutes=15)
    assert any("failure_code is missing" in a for a in result["anomalies"])


def test_failed_with_failure_code_not_flagged_for_that_reason():
    txn = make_txn(status="FAILED", completed_at=NOW, failure_code="UPSTREAM_ERROR",
                    callbacks=[{"attempt_no": 1, "http_status": 500, "callback_status": "FAILED", "attempted_at": NOW}])
    result = analyze_transaction(txn, NOW, stuck_threshold_minutes=15)
    assert not any("failure_code is missing" in a for a in result["anomalies"])


def test_multiple_failed_callbacks_flagged():
    txn = make_txn(
        status="FAILED",
        failure_code="UPSTREAM_ERROR",
        completed_at=NOW,
        callbacks=[
            {"attempt_no": 1, "http_status": 500, "callback_status": "FAILED", "attempted_at": NOW},
            {"attempt_no": 2, "http_status": 500, "callback_status": "FAILED", "attempted_at": NOW},
        ],
    )
    result = analyze_transaction(txn, NOW, stuck_threshold_minutes=15)
    assert any("failed callback attempts" in a for a in result["anomalies"])


def test_build_report_flags_duplicates():
    txn1 = make_txn(id=1)
    txn2 = make_txn(id=2)
    report = build_report("TXN00000001", [txn1, txn2], NOW, stuck_threshold_minutes=15)
    assert report["match_count"] == 2
    assert "duplicate_reference_warning" in report


def test_build_report_no_warning_for_single_match():
    txn1 = make_txn(id=1)
    report = build_report("TXN00000001", [txn1], NOW, stuck_threshold_minutes=15)
    assert "duplicate_reference_warning" not in report
