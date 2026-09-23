# Architecture

## Components
```
┌─────────────┐      ┌──────────────────┐      ┌────────────┐
│  Browser UI │ ───► │  MiniPay API      │ ───► │ PostgreSQL │
│ (static JS) │      │  (FastAPI, :8080) │      │  (:5432)   │
└─────────────┘      └──────────────────┘      └────────────┘
                              ▲
                              │ direct DB queries
                              │ (bypasses the API on purpose --
                              │  see "Python CLI" below)
                       ┌──────────────┐
                       │ support_tool │
                       │    (CLI)     │
                       └──────────────┘
```
The UI is served *by* the API process as static files (`app/minipay_api/static/`)
rather than as a separate container. This is a deliberate simplification
for a small assessment app — documented here rather than silently taken:
a production MiniPay would likely split these (different scaling/caching
characteristics, different deploy cadence), but for a single-page
support console with no build step, one fewer moving part was judged more
valuable than the architectural purity of a separate frontend service.
`requirements/03-kubernetes-rancher.md` accepts "UI/API/database **or
equivalent components**," which is the basis for this choice.

## Why plain psycopg2, not an ORM
Query behaviour needs to be exactly legible during troubleshooting (this
is an L2/support-tooling assessment) — an ORM's generated SQL is one more
layer to reason through when diagnosing something like INCIDENT-001. The
trade-off (more boilerplate, manual `RealDictCursor` row handling) was
judged acceptable at this scale.

## Idempotency design
`POST /api/payments` treats `transaction_ref` as an idempotency key: a
replayed request with the same ref returns the existing record
(`idempotent_replay: true`, HTTP 200, not 201). This is the direct,
intentional mitigation for the class of problem described in
`tests/api/NOTES.md` (client timeout → safe retry). It does **not**
retroactively fix the historical duplicate refs already in the seeded
dataset — see `investigation/INCIDENT-001-RCA.md` for why those still
exist and what would need to happen to fully close that gap (a
backfill/cleanup migration before a `UNIQUE` constraint could be added).

## Synchronous settlement simplification
`POST /api/payments` decides `SUCCESS` vs. `PROCESSING` synchronously
based on `amount < 5000` (see the comment in `app/minipay_api/main.py`).
A real payment processor's result arrives asynchronously via a callback,
which is why `callbacks` exists as a table at all — but building a real
async settlement flow (webhook receiver, retry/backoff scheduler) was out
of scope for what this assessment needs to exercise (SQL, K8s, CLI
diagnostics, API/UI testing). This simplification is called out here
explicitly rather than left for a reviewer to discover.

## Auth
A single shared API key (`X-API-Key` header) is deliberately minimal —
explicitly acceptable per `requirements/05-web-services-api-tests.md`
("a simple mechanism is acceptable"). Real MiniPay would need per-client
credentials and probably OAuth2/mTLS; not built here because it would add
scope without exercising anything the assessment asks for.

## Health vs. liveness split
`/health` checks DB connectivity (suitable for a Kubernetes
**readiness** probe — remove an unhealthy pod from load balancing).
`/livez` only checks that the process is responsive (suitable for
**liveness** — restart only if the process itself is stuck). This split
exists specifically because of a bug found during the Kubernetes
investigation: see `investigation/kubernetes-findings.md` finding #9 and
`investigation/INCIDENT-002-RCA.md`. Conflating the two causes
self-inflicted restart loops during a database incident — the application
would be punished (restarted) for a dependency's outage it has no control
over.

## Why the support CLI queries the database directly, not the API
`python/support_tool.py` needs callback/retry history, which no API
endpoint currently exposes, and needs to be resilient to the exact
duplicate-`transaction_ref` condition that crashes the API's own search
endpoint (INCIDENT-001) — an L2 diagnostic tool that breaks on the same
data quality issue it's meant to help diagnose would be actively
counterproductive. Direct DB access is documented here as an explicit
trade-off: it couples the CLI to the schema rather than an API contract,
which would need revisiting if the schema became genuinely private to the
API team.

## What's simplified or intentionally out of scope
- No real payment-gateway integration (this is a self-contained demo of
  the *shape* of such a system, not a production payments processor).
- No multi-tenant auth, no rate limiting, no audit log beyond the request
  logging middleware and Postgres's own WAL.
- `docker-compose.yml` uses plaintext dev credentials appropriate only
  for local development, never committed for any non-local environment
  (see `kubernetes/02-secret.example.yaml` for how real deployments
  differ).
