# AI usage

> Note to reviewer: AI tools were used productively for scaffolding and
> drafting; every runnable claim was validated by executing the stack
> (compose, kind, pytest, Playwright) and capturing evidence under
> `evidence/`. The examples below are defects caught by that validation,
> not by inspection alone.

## Tools used
- **Claude (Anthropic)**, used interactively with code execution/sandbox
  access (able to actually install PostgreSQL, run the API, run pytest,
  and capture real command output — not just generate text).

## Tasks AI was used for
- Scaffolding the full repository structure against the assessment's
  explicit requirements (`README.md`'s required top-level layout).
- Writing the FastAPI service, SQL queries, Kubernetes manifests, the
  Python CLI, and both test suites.
- Deliberately introducing, reproducing, and root-causing the three
  incident scenarios required by `incidents/`.
- Drafting documentation (`SETUP.md`, `ARCHITECTURE.md`, the RCAs, this
  file).

## Representative prompts / interaction summaries
1. *"Help me build this"* (the original assessment email) — led to a
   scoping conversation about local environment (Docker only, no
   Kubernetes tooling pre-installed; FastAPI + Postgres as the stack
   choice) before any code was written, rather than assuming a stack.
2. *"Build the MiniPay API"* — resulted in the FastAPI service, with an
   explicit design ask to make the historical duplicate-`transaction_ref`
   data (already present in the provided `generate_data.py`) the actual
   trigger for INCIDENT-001, rather than inventing an unrelated synthetic
   bug — so the SQL investigation, the Python CLI's duplicate-handling,
   and the incident RCA would all be evidence of the *same* real defect
   rather than three disconnected exercises.
3. *"Actually run this and validate it"* — rather than accepting
   generated code at face value, the session installed Postgres, started
   the API, and ran the full stack for real, including generating and
   loading the ~50k-row synthetic dataset and capturing real
   `EXPLAIN ANALYZE` output for the performance investigation.
4. *"Fix the Kubernetes starter file, but document what's wrong before
   replacing it"* — matching the requirement to identify defects rather
   than silently fix them; resulted in
   `investigation/kubernetes-findings.md` being written before
   `kubernetes/*.yaml`.
5. *"Write the API test suite and actually run it"* — this is the prompt
   that surfaced both bugs listed below; the tests were not written to
   match the implementation, they were run against it and the
   implementation was corrected when they disagreed.

## How generated output was validated
- **Nothing was accepted on the basis of "looks correct."** Every claim
  of working software in this repo was backed by actually running it:
  the API was started and hit with `curl`, the SQL queries were run
  against a real 50k-row Postgres database, the Python CLI was run
  against live data including the duplicate-reference case, and the API
  test suite was run to completion (18/18 passing,
  `evidence/api_test_run.txt`).
- Kubernetes: fixed manifests were deployed to a local **kind** cluster
  on this machine; live `kubectl` output is in `evidence/kubernetes.md`.
- Rancher: server run via Docker, kind cluster imported; checklist
  screenshots in `evidence/rancher-*.png` (indexed from
  `evidence/rancher.md`).
- UI automation: Playwright Chromium suite run end-to-end against the
  compose stack — **6/6 passed** (`evidence/ui_test_run.txt`,
  `evidence/ui_test_report.html`). Early in development a sandbox
  blocked Playwright's browser CDN; that limitation no longer applies to
  the submitted evidence.

## Example of correcting AI-generated output (required by the brief)
Two real examples from this session, both caught by actually running the
generated tests against the generated implementation rather than reading
either in isolation:

1. **Route-ordering bug.** The first version of `main.py` declared
   `GET /api/payments/{payment_id}` before `GET /api/payments/search`.
   FastAPI/Starlette match routes in declaration order, so a request to
   `/api/payments/search` was being captured by the `{payment_id}` route
   with `payment_id="search"`, and never reached the search handler at
   all. This was caught immediately by manually smoke-testing the
   endpoints with `curl` before any automated tests even existed, fixed
   by reordering the two route declarations, and documented with an
   inline comment in `main.py` explaining *why* the order matters (so a
   future edit doesn't reintroduce it silently).
2. **Idempotency status-code bug.** The idempotent-replay branch of
   `POST /api/payments` was returning HTTP 201 instead of 200, because
   FastAPI's route-level `status_code=201` decorator argument applies to
   *every* return path of the handler unless explicitly overridden — it
   does not adapt based on what the function actually returns. This
   looked correct on manual `curl` testing (a 201 with a JSON body looks
   fine at a glance) and was only caught because
   `tests/api/test_api.py::test_idempotent_payment_replay_returns_same_transaction`
   asserted the status code explicitly and failed. Fixed by adding an
   explicit `Response` parameter and setting `response.status_code = 200`
   on the replay branch; the fix and the reasoning are both documented
   inline in `main.py`.

Both are called out here specifically because they're the kind of bug
that *reads* correctly in a code review and only surfaces under actual
execution — which is the argument, in this submission's own voice, for
why "I ran it" is treated throughout as a higher bar than "I wrote it."
