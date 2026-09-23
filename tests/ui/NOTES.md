# UI test notes

## Running the suite
```bash
cd tests/ui
pip install -r requirements.txt
playwright install chromium
export MINIPAY_UI_URL=http://localhost:8080 MINIPAY_API_KEY=dev-local-key
pytest -v --browser chromium --html=../../evidence/ui_test_report.html --self-contained-html
```
(requires the API running — see `SETUP.md`; add `pytest-html` to
`requirements.txt` if you want the HTML report flag above, or drop
`--html`/`--self-contained-html` and just use `-v` output.)

## Evidence
End-to-end run on this machine against the live compose stack
(`SETUP.md` §1 + §6):

- Console log: `evidence/ui_test_run.txt` — **6 passed** in ~8s (Chromium)
- HTML report: `evidence/ui_test_report.html`

Early scaffolding was done in a sandbox that blocked Playwright's
browser CDN; the submitted evidence is from a full unrestricted run.

## Selector strategy
Every interactive element has a `data-testid` attribute (see
`app/minipay_api/static/index.html`). Tests use Playwright's
`get_by_test_id()` exclusively — never CSS classes (which are for styling
and change independently of behaviour) or raw text (which changes with
copy edits). Waits are all `element.wait_for(state="visible")` on the
specific result element the action populates, i.e. waiting for an
application state change, not `page.wait_for_timeout()` / sleeps.

## CI integration
- **Every release / every PR (fast gate):** the API suite
  (`tests/api`, ~0.4s for 18 tests against a throwaway Postgres container)
  plus `test_login_with_valid_key_succeeds`,
  `test_search_existing_transaction_shows_result`, and
  `test_submit_payment_shows_success_result` from this suite — the
  minimum needed to prove the three core user journeys aren't broken.
  Target: a few seconds to low tens of seconds; blocks the merge/deploy.
- **Larger regression suite (nightly / pre-release, not every commit):**
  the remaining negative-path UI tests, a full cross-browser matrix
  (chromium/firefox/webkit), and anything slower or more flaky-prone
  (e.g. visual regression, if added later). This tier is allowed to take
  minutes and is not a merge gate — it's a signal reviewed before a
  release goes out, not something that blocks every commit.
- Both tiers run headless in CI with the API+DB started via
  `docker compose up -d` first (see `.github/workflows/ci.yml`), and
  Playwright's own trace-on-failure feature is enabled so a failing run
  in CI produces a debuggable artifact, not just a red X.
