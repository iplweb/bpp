# Claude Code Web Environment — Notes

Cloud sandbox setup runs automatically via the `SessionStart`
hook in `.claude/hooks/setup-cloud.sh`. No manual steps needed.

## Running tests

Playwright browsers cannot be downloaded in the sandbox
(cdn.playwright.dev is not whitelisted). Run tests excluding
Playwright tests:

```bash
uv run pytest -m "not playwright" --maxfail 50
```

**Full test run (without Playwright) takes ~55 minutes** in
the sandbox environment on a single worker.

## Known sandbox-specific test failures

These are **not real bugs** — they pass on a normal machine:

- Tests using VCR cassettes for external APIs (CrossRef, DOI)
  fail because the egress proxy changes the host/port in
  requests.
- Affected test files:
  - `src/bpp/tests/test_admin/test_crossref_api_helpers.py`
  - `src/bpp/tests/test_admin/test_crossref_api_sync.py`
  - `src/importer_publikacji/tests/test_views.py`
  - `src/pbn_import/tests/test_admin_compression.py`

## Docker

Docker builds (`make build`, `docker compose up`) do not work
in the sandbox because Docker image layer CDN
(`*.r2.cloudflarestorage.com`) is not in the proxy allowlist.
