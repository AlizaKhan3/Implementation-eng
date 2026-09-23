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
evidence/                -- real captured command output, health-check script, Rancher procedure
.github/workflows/ci.yml -- CI pipeline
docker-compose.yml       -- local reproduction environment
```

## Requirement → where to look
| Requirement | Where |
|---|---|
| Linux | `evidence/linux.md`, `evidence/healthcheck.sh` |
| Git | this repo's own commit history + `submission-v1.0` tag |
| SQL & data investigation | `sql/`, `evidence/sql_query_outputs.md` |
| Kubernetes & Rancher | `kubernetes/`, `investigation/kubernetes-findings.md`, `evidence/rancher.md` |
| Python support utility | `python/support_tool.py` |
| API automation | `tests/api/` |
| UI automation | `tests/ui/`, `app/minipay_api/static/index.html` |
| Troubleshooting / incidents | `investigation/INCIDENT-00{1,2,3}-RCA.md` |
| AI usage | `AI_USAGE.md` |

## What's genuinely complete vs. outstanding
Everything above was built and, where the environment allowed, **actually
run and validated** — not just written. Two things are explicitly
incomplete and documented as such rather than glossed over:
- **Live Kubernetes deployment evidence** (`kubectl get pods`, etc.) —
  the manifests are written and reasoned through defect-by-defect in
  `investigation/kubernetes-findings.md`, but the build environment had
  no Docker/Kubernetes runtime to deploy them to. See
  `investigation/INCIDENT-002-RCA.md`'s honesty note and `SETUP.md` §7
  for the exact commands to complete this.
- **Rancher evidence** — same underlying blocker; see `evidence/rancher.md`
  for the exact procedure to complete it.
- **UI test execution** — the Playwright suite is written and verified to
  collect correctly (`pytest --collect-only`), but couldn't run
  end-to-end because the build sandbox's network policy blocked
  Playwright's browser-binary download. See `tests/ui/NOTES.md`.

Everything else (the API, all 7 SQL queries, the performance
investigation, the Python CLI, the API test suite, all 3 incident RCAs)
was run for real against a live PostgreSQL instance and a live API
process during development, with real captured output as evidence.

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
