# Changelog

## Unreleased

- Automatic retries with exponential backoff (`retries=`, `backoff=` on `TarmacClient`). Swap requests are never re-sent after a network failure.

## 0.1.0

- First release: `TarmacClient`, `run_agent`, `attach`, typed tools and `TarmacToolError`. Standard library only.
