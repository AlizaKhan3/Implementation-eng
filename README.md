# MiniPay — Paysys Labs Implementation/L2 Technical Assessment

A small payment-processing service (API + UI + PostgreSQL) built,
deployed, tested, and debugged end-to-end for the assessment described in
the original repo: https://github.com/karimjindani/paysys-implementation-l2-assessment

**Quick start:** `docker compose up --build`, then see `SETUP.md` for
everything else (SQL, Kubernetes, tests, the CLI).

## Repository structure
```
README.md, SETUP.md, ARCHITECTURE.md, AI_USAGE.md   -- top-level docs (this file + 3 more)
app/minipay_api/         -- the MiniPay FastAPI service + embedded static UI
database/                -- schema.sql, generate_data.py (both from the assessment starter, unmodified),
                             migrations/ (indexes added during the performance investigation)
sql/                     -- the 7 required investigation queries + PERFORMANCE.md
kubernetes/              -- fixed manifest set (+ the original broken file, preserved)
python/                  -- support_tool.py CLI + its unit tests
tests/api/                -- pytest API test suite + NOTES.md
tests/ui/                 -- Playwright UI test suite + NOTES.md
investigation/           -- kubernetes-findings.md + the 3 incident RCAs
evidence/                -- captured command output, Rancher screenshots, health-check script, test run logs
.github/workflows/ci.yml -- CI pipeline
docker-compose.yml       -- local reproduction environment
```

## Requirement → where to look
| Requirement | Where |
|---|---|
| Linux | `evidence/linux.md`, `evidence/healthcheck.sh` |
| Git | this repo's own commit history + `submission-v1.0` tag |
| SQL & data investigation | `sql/`, `evidence/sql_query_outputs.md` |
| Kubernetes & Rancher | `kubernetes/`, `investigation/kubernetes-findings.md`, `evidence/kubernetes.md`, `evidence/rancher.md` (+ screenshots) |
| Python support utility | `python/support_tool.py` |
| API automation | `tests/api/`, `evidence/api_test_run.txt` |
| UI automation | `tests/ui/`, `evidence/ui_test_run.txt`, `evidence/ui_test_report.html` |
| Troubleshooting / incidents | `investigation/INCIDENT-00{1,2,3}-RCA.md` |
| AI usage | `AI_USAGE.md` |

## What's complete
All requirement areas were built and **run for real**, with captured
evidence under `evidence/`:
- Linux checks + `healthcheck.sh` → `evidence/linux.md`
- SQL (7 queries + performance) → `evidence/sql_query_outputs.md`, `sql/PERFORMANCE.md`
- Kind deploy of fixed manifests → `evidence/kubernetes.md`
- Rancher (imported kind cluster, checklist screenshots) → `evidence/rancher.md`
- Python CLI + unit tests → `python/`
- API suite **18/18** → `evidence/api_test_run.txt`
- Playwright UI suite **6/6** (Chromium) → `evidence/ui_test_run.txt`
- Three incident RCAs → `investigation/`

**Known limitation (documented, not hidden):** INCIDENT-001 permanently
stops *new* duplicate `transaction_ref` creation via idempotent create,
but `/api/payments/search` still returns 500 for *pre-existing* seeded
duplicates until a UNIQUE constraint + backfill is applied. See
`investigation/INCIDENT-001-RCA.md`.

## Git / branch strategy
Single-branch (`main`), linear history, one meaningful commit per
logical unit of work (DB/schema → API → Kubernetes fix → Python CLI →
tests/CI → incidents/evidence → docs), each with a commit message
explaining *why*, not just *what*. No feature branches were used given
the solo, sequential nature of the work; a team setting would instead use
short-lived branches per requirement area with PR review before merge to
`main`, particularly around the Kubernetes and incident-response pieces
where a second reviewer catching a missed defect has real value. The
final commit is tagged `submission-v1.0`.

## AI usage
Disclosed in full in `AI_USAGE.md`, including two examples of bugs in
AI-generated code that were caught by actually running the test suite
against it, not by inspection.
