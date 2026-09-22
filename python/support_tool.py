#!/usr/bin/env python3
"""MiniPay L2 support diagnostic tool.

Usage:
    python support_tool.py --transaction TXN000123
    python support_tool.py --transaction TXN000123 --json
    python support_tool.py --stuck-report
    python support_tool.py --healthcheck

Configuration is via environment variables (DB_HOST, DB_PORT, DB_NAME,
DB_USER, DB_PASSWORD, MINIPAY_API_URL, MINIPAY_API_KEY, MINIPAY_TIMEOUT,
MINIPAY_STUCK_MINUTES) -- see minipay_support/config.py. No credentials
are hard-coded.

Exit codes:
  0 - success, no anomalies found
  1 - transaction not found
  2 - anomalies detected (informational; use --json for scripting)
  3 - could not reach the database and/or API (connectivity/timeout)
  4 - unexpected internal error
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone

from minipay_support.config import Config
from minipay_support.db import cursor, db_healthcheck
from minipay_support.api_client import api_healthcheck
from minipay_support.report import build_report, fetch_stuck_transactions, fetch_transaction_records
from minipay_support.formatting import render_json, render_text

logger = logging.getLogger("support_tool")


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,  # keep stdout clean for --json / report output
    )


def cmd_transaction(cfg: Config, ref: str, as_json: bool) -> int:
    try:
        with cursor(cfg) as cur:
            txns = fetch_transaction_records(cur, ref)
    except Exception as exc:  # noqa: BLE001
        logger.error("Could not query the database: %s", exc)
        return 3

    if not txns:
        msg = f"No transaction found with reference {ref!r}"
        if as_json:
            print(render_json({"queried_ref": ref, "match_count": 0, "matches": [], "error": msg}))
        else:
            print(msg)
        return 1

    report = build_report(ref, txns, datetime.now(timezone.utc).replace(tzinfo=None), cfg.stuck_threshold_minutes)
    print(render_json(report) if as_json else render_text(report))

    any_anomaly = any(m["anomalies"] for m in report["matches"])
    return 2 if any_anomaly else 0


def cmd_stuck_report(cfg: Config, as_json: bool) -> int:
    try:
        with cursor(cfg) as cur:
            stuck = fetch_stuck_transactions(cur, cfg.stuck_threshold_minutes)
    except Exception as exc:  # noqa: BLE001
        logger.error("Could not query the database: %s", exc)
        return 3

    if as_json:
        import json

        print(
            json.dumps(
                [
                    {
                        "id": r["id"],
                        "transaction_ref": r["transaction_ref"],
                        "customer_id": r["customer_id"],
                        "amount": str(r["amount"]),
                        "created_at": r["created_at"].isoformat(),
                    }
                    for r in stuck
                ],
                indent=2,
            )
        )
    else:
        print(f"{len(stuck)} transaction(s) stuck in PROCESSING > {cfg.stuck_threshold_minutes} minutes:")
        for r in stuck:
            print(f"  id={r['id']} ref={r['transaction_ref']} amount={r['amount']} created_at={r['created_at']}")

    return 2 if stuck else 0


def cmd_healthcheck(cfg: Config, as_json: bool) -> int:
    db_ok, db_msg = db_healthcheck(cfg)
    api_ok, api_msg = api_healthcheck(cfg)
    result = {
        "database": {"ok": db_ok, "detail": db_msg},
        "api": {"ok": api_ok, "detail": api_msg},
    }
    if as_json:
        import json

        print(json.dumps(result, indent=2))
    else:
        print(f"Database: {'OK' if db_ok else 'FAIL'} ({db_msg})")
        print(f"API:      {'OK' if api_ok else 'FAIL'} ({api_msg})")
    return 0 if (db_ok and api_ok) else 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MiniPay L2 support diagnostic tool")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--transaction", metavar="REF", help="diagnose a single transaction by reference")
    group.add_argument(
        "--stuck-report", action="store_true", help="list transactions stuck in PROCESSING past the threshold"
    )
    group.add_argument("--healthcheck", action="store_true", help="check API and database connectivity")
    parser.add_argument("--json", action="store_true", help="machine-readable JSON output")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging on stderr")
    args = parser.parse_args(argv)

    _setup_logging(args.verbose)
    cfg = Config()

    try:
        if args.transaction:
            return cmd_transaction(cfg, args.transaction, args.json)
        if args.stuck_report:
            return cmd_stuck_report(cfg, args.json)
        if args.healthcheck:
            return cmd_healthcheck(cfg, args.json)
    except Exception:  # noqa: BLE001
        logger.exception("Unexpected error")
        return 4
    return 4  # unreachable: argparse's required mutually-exclusive group


if __name__ == "__main__":
    sys.exit(main())
