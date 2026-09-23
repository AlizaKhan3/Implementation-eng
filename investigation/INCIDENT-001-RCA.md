# INCIDENT-001 – Intermittent Transaction Search Failure

**Priority:** P2 · **Status:** Root-caused and fixed in this submission

## Observations (as reported)
Users report that transaction searches (`GET /api/payments/search?ref=...`)
intermittently return HTTP 500. Some transaction references work; others
fail. No pattern was obvious from the outside.

## Note on how this was investigated
This defect was **not left to chance** — it's deliberately built into this
submission's implementation on purpose, per the incident brief ("where
your own implementation does not naturally reproduce this fault,
deliberately introduce a realistic defect"). The reason it's realistic
rather than contrived: `database/schema.sql` (provided, unmodified) never
declares `transaction_ref` `UNIQUE`, and `database/generate_data.py`
(also provided, unmodified) deliberately seeds a handful of duplicate
`transaction_ref` values (confirmed independently via
`sql/04_duplicate_refs.sql` — 10 duplicate pairs in the 50k-row seed).
`app/minipay_api/main.py`'s search handler assumes exactly one row comes
back. That combination — a real, pre-existing data-quality gap plus code
that doesn't defend against it — *is* the intermittent bug; nothing about
the failure mode itself was invented, only the trigger (a second insert)
was added to demonstrate it on demand instead of waiting for it to occur
in production data.

## Reproduction steps and evidence
Full command transcript: `evidence/incident-001-reproduction.md`. Summary:

1. `GET /api/payments/search?ref=TXN00030001` → **200 OK** (ref matches
   exactly one row).
2. Insert a second `transactions` row with the same `transaction_ref`
   (simulating the kind of duplicate the seed generator already produces
   naturally elsewhere in the dataset).
3. Repeat the identical search → **500 Internal Server Error**.
4. Application log shows the exact failure point:
   ```
   (row,) = rows  # <-- intentional defect: fails when duplicates exist
   ValueError: too many values to unpack (expected 1)
   ```

This matches the reported symptom precisely: **which** refs fail is a
function of the data (does this specific ref happen to have a duplicate
row?), not of the request itself — hence "some IDs work, others fail,"
appearing intermittent from the outside while actually being fully
deterministic per-ref.

## Hypotheses considered
| Hypothesis | Status | Why |
|---|---|---|
| Network flakiness / load balancer | Rejected | Reproduces 100% of the time for an affected ref, 0% for others — not timing-dependent. |
| DB connection pool exhaustion | Rejected | Failure is instant and independent of concurrent load; single-request reproduction is enough. |
| Malformed `ref` query parameter | Rejected | The exact same, well-formed ref string succeeds before the duplicate is inserted and fails after — the ref format isn't the variable. |
| Unhandled multi-row result in the search handler | **Confirmed** | Traceback points directly at `(row,) = rows` in `main.py`; matches the reported "some IDs work, others fail" pattern exactly. |

## Root cause
`GET /api/payments/search` assumes `transaction_ref` uniquely identifies
a row and unpacks the result set with `(row,) = rows`, which raises
`ValueError` for any ref with more than one matching row. There is no
database-level `UNIQUE` constraint on `transaction_ref` to prevent such
duplicates from existing in the first place, so the assumption in the
code was never actually guaranteed by the schema.

## Immediate corrective action
None required in production data for this submission (no real incident
occurred) — but the documented immediate action, if this happened live,
would be: identify affected refs via `sql/04_duplicate_refs.sql`, and for
each one, manually determine via `python/support_tool.py --transaction
<ref>` (which does **not** share this bug — see below) which row is the
authoritative one, since the search endpoint itself cannot be trusted for
those specific refs until the permanent fix ships.

## Permanent corrective / preventive action
1. **Made `POST /api/payments` idempotent on `transaction_ref`** (see
   `app/minipay_api/main.py`): replaying the same ref now returns the
   existing transaction instead of inserting a second row, so *new*
   duplicates stop being created. This does not clean up any that already
   exist, but stops the bleeding.
2. **The support CLI queries duplicates safely on purpose**
   (`python/minipay_support/report.py::fetch_transaction_records`
   explicitly fetches *all* matching rows and surfaces a
   `duplicate_reference_warning` rather than assuming one — see
   `python/tests/test_report.py::test_build_report_flags_duplicates`).
   This was a deliberate design choice specifically because of this
   incident, not an accident.
3. **Regression test added**:
   `tests/api/test_api.py::test_search_with_duplicate_ref_returns_500`
   documents the current (defective) behaviour so it can't silently
   regress further, and is annotated to be updated once remediation (4)
   below ships.
4. **Recommended but not yet applied in this submission** (flagged
   honestly as a limitation): add a `UNIQUE` constraint on
   `transactions.transaction_ref` once the existing ~10 duplicate pairs
   in historical/seed data are reconciled (a real production rollout
   would need a backfill/cleanup migration first, since you cannot add a
   `UNIQUE` constraint over data that already violates it). Until that
   lands, `/api/payments/search` should be changed to return a list (or a
   409 with both candidates) instead of assuming a single result — this
   is a more defensive fix than the idempotency safeguard alone provides
   for the *existing* duplicates.

## Validation performed after the fix
- `tests/api/test_api.py::test_idempotent_payment_replay_returns_same_transaction`
  passes, confirming new duplicates are no longer created via the normal
  payment-creation path (18/18 tests pass — see `evidence/api_test_run.txt`).
- `python/support_tool.py --transaction TXN00004999 --json` (a ref with a
  genuine seeded duplicate) was run against the live 50k-row dataset and
  correctly returns both matches with a `duplicate_reference_warning`
  instead of crashing — see the worked example in
  `python/support_tool.py`'s own smoke test output during development.
- The search endpoint itself (item 4 above) is **not yet fixed** for
  already-existing duplicates — this is called out explicitly rather than
  claiming full remediation; `test_search_with_duplicate_ref_returns_500`
  exists precisely to keep that gap visible instead of silently passing.
