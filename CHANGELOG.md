# Changelog

## Unreleased

- Automatic retries with exponential backoff (`retries=`, `backoff=` on `TarmacClient`). Swap requests are never re-sent after a network failure.
- `TarmacClient.from_env()` and `attach_from_env()` read `TARMAC_URL`, `TARMAC_RUN_ID` and `TARMAC_RUN_TOKEN`.
- New example: `careful_vs_reckless.py`.
- Release workflow: tagged versions publish to PyPI via Trusted Publishing. The version now lives in one place (`_version.py`).

## 0.1.0

- First release: `TarmacClient`, `run_agent`, `attach`, typed tools and `TarmacToolError`. Standard library only.
