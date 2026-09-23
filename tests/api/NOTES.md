# Notes: timeouts, retries, idempotency, 4xx vs 5xx

## Running the suite
```bash
cd tests/api
pip install -r ../../app/minipay_api/requirements.txt -r requirements.txt
export MINIPAY_API_URL=http://localhost:8080 MINIPAY_API_KEY=dev-local-key \
       DB_HOST=localhost DB_PORT=5432 DB_NAME=minipay DB_USER=minipay DB_PASSWORD=minipay
pytest -v
```
(requires the API + DB running — `docker compose up --build` from the repo
root, or the manual steps in `SETUP.md`.) Real output from a passing run
(18/18) is saved in `evidence/api_test_run.txt`.

## Client/server timeouts
- The support CLI (`python/`) sets an explicit `connect_timeout` on every
  DB connection and every `requests` call (`MINIPAY_TIMEOUT`, default 5s)
  and treats a timeout as a distinct, reported failure mode rather than
  hanging — see `minipay_support/api_client.py`.
- For the API itself: a payment gateway integration should set both a
  connect timeout and a read timeout on any outbound call to an upstream
  processor, and those two numbers should differ (connect timeout short,
  read timeout longer since settlement can legitimately take seconds). A
  request that times out is **not** the same as a request that failed —
  the money side may have succeeded even though the response never came
  back, which is exactly why idempotency (below) matters.

## Retries
- Only safe to retry automatically when the operation is idempotent (see
  below) **and** the failure mode is one where "unknown outcome" is a
  reasonable interpretation — i.e., timeouts and 5xx/connection errors.
  Never blindly retry a 4xx: the request was understood and rejected, and
  retrying it unchanged will fail identically.
- Retries should use bounded exponential backoff with jitter, and a
  retry budget (a handful of attempts, not "until it works") — this
  mirrors why `callbacks.attempt_no` exists in the schema: the system
  already models "we tried N times."

## Idempotency
- `POST /api/payments` requires (or generates) a `transaction_ref` and
  treats it as the idempotency key: replaying the same ref returns the
  existing transaction with `idempotent_replay: true` and **HTTP 200**,
  not 201 — no new resource is created. This was actually broken during
  development (the route decorator's `status_code=201` silently applied
  to every return path, including the replay branch) and caught by
  `test_idempotent_payment_replay_returns_same_transaction`; see
  `AI_USAGE.md` for that as a worked example of catching AI-authored
  output that looked right but wasn't. See fixed code + the inline
  comment in `app/minipay_api/main.py`.
- Idempotency is the direct mitigation for the retry problem above: a
  client that times out waiting for a response can safely retry the exact
  same request body without risking a duplicate charge, *provided* the
  ref stays stable across the retry (i.e., generated once client-side,
  not re-generated per attempt).

## HTTP 4xx vs 5xx
- 4xx means the request itself was the problem (bad input, unknown
  resource, missing/invalid auth) — the client should not retry unchanged;
  it should fix the request. Covered here: 401 (missing/invalid API key),
  404 (unknown customer/payment/search ref), 422 (validation: missing
  field, non-positive amount).
- 5xx means the server failed to do its job on an otherwise-valid request
  — safe to retry (with backoff), and worth alerting on. Covered here by
  `test_search_with_duplicate_ref_returns_500`, which deliberately
  reproduces INCIDENT-001 (see `investigation/INCIDENT-001-RCA.md`): a
  valid, well-formed search request against data with a duplicate
  `transaction_ref` currently 500s because the handler assumes
  uniqueness. That's a real defect this suite documents, not a
  hypothetical — the test will need updating once the permanent fix
  (making `transaction_ref` unique, or making the handler duplicate-safe)
  ships.
