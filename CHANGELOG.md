# Changelog

## 0.1.0

First release on PyPI.

- `TarmacClient`, `run_agent`, `attach`, typed tools and `TarmacToolError`. Standard library only.
- Automatic retries with exponential backoff (`retries=`, `backoff=` on `TarmacClient`). Swap requests are never re-sent after a network failure.
- `TarmacClient.from_env()` and `attach_from_env()` read `TARMAC_URL`, `TARMAC_RUN_ID` and `TARMAC_RUN_TOKEN`.
- Examples: `quickstart.py` and `careful_vs_reckless.py`.
