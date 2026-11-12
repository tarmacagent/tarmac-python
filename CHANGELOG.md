# Changelog

## Unreleased

- `python -m tarmac_agent check` tells you whether a server is reachable and which run modes it serves. Reads `$TARMAC_URL` or `--url`.
- `TarmacClient.health()` returns the same status from code.
- `python -m tarmac_agent --version`.

## 0.1.0

First release on PyPI.

- `TarmacClient`, `run_agent`, `attach`, typed tools and `TarmacToolError`. Standard library only.
- Automatic retries with exponential backoff (`retries=`, `backoff=` on `TarmacClient`). Swap requests are never re-sent after a network failure.
- `TarmacClient.from_env()` and `attach_from_env()` read `TARMAC_URL`, `TARMAC_RUN_ID` and `TARMAC_RUN_TOKEN`.
- Examples: `quickstart.py` and `careful_vs_reckless.py`.
