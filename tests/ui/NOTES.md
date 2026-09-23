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

## Honesty note on evidence
`pytest --collect-only` in the development sandbox confirms all 6 tests
collect correctly against real fixtures and selectors (no syntax/import
errors) — output:
```
collected 6 items
<Function test_login_with_valid_key_succeeds[chromium]>
<Function test_login_with_invalid_key_fails[chromium]>
<Function test_search_existing_transaction_shows_result[chromium]>
<Function test_submit_payment_shows_success_result[chromium]>
<Function test_search_nonexistent_transaction_shows_error[chromium]>
<Function test_submit_payment_for_unknown_customer_shows_error[chromium]>
```
The sandbox used to build this submission has a restricted network egress
allowlist that does not include Playwright's browser-binary CDN
(`playwright.azureedge.net` and mirrors), so `playwright install chromium`
fails there with `403 Host not in allowlist`, and the suite could not be
executed end-to-end in that environment. **Run it for real on an
unrestricted machine before submitting** and drop the actual pass/fail
output (or `evidence/ui_test_report.html`) into `evidence/`. Do not
represent this as having been executed if it hasn't — see `AI_USAGE.md`
for why this is called out explicitly.

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
