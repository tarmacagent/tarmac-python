# tarmac-agent

[![ci](https://github.com/tarmacagent/tarmac-python/actions/workflows/ci.yml/badge.svg)](https://github.com/tarmacagent/tarmac-python/actions/workflows/ci.yml) ![python](https://img.shields.io/badge/python-3.10%2B-black) ![deps](https://img.shields.io/badge/dependencies-0-black) ![license](https://img.shields.io/badge/license-MIT-black)

**Test your on-chain agent before it goes live, from Python.**

Tarmac runs your agent against a live fork of Robinhood Chain with an isolated simulated wallet, applies the same policy checks to every swap request, and records a trace of every tool call, check and balance change. Your agent runs on your machine and never holds a key.

```bash
pip install tarmac-agent
```

> **Coming to PyPI soon.** Until the first release lands, install straight from GitHub:
>
> ```bash
> pip install "git+https://github.com/tarmacagent/tarmac-python"
> ```

Standard library only: no dependencies.

## Quickstart

```python
from tarmac_agent import TarmacClient, TarmacTools, run_agent

client = TarmacClient("https://your-tarmac-server")

def my_agent(tools: TarmacTools) -> None:
    ctx = tools.get_context()
    pair = dict(token_in=ctx["tokenIn"]["address"], token_out=ctx["tokenOut"]["address"])
    quote = tools.get_quote(**pair, amount_in=ctx["amountIn"])

    if quote["slippageBps"] > ctx["policy"]["maxSlippageBps"]:
        tools.finish("stopped", "Slippage over the limit.")
        return

    tools.request_swap(quote_id=quote["quoteId"], **pair, amount_in=ctx["amountIn"])
    tools.finish("swapped")

out = run_agent(client, my_agent, scenario="swap-thin", agent_name="my-python-agent")
print(out["run"]["result"]["verdictLabel"])  # "Followed the rule and stopped"
print(out["session"].run_url)                  # full trace in the browser
```

### Servers that require sign-in

Create the run in the Tarmac app (**Run → Your agent**), then attach:

```python
run_agent(client, my_agent, run_id=os.environ["TARMAC_RUN_ID"], run_token=os.environ["TARMAC_RUN_TOKEN"])
```

### From environment variables

```python
client = TarmacClient.from_env()          # $TARMAC_URL, default http://localhost:3000
session = client.attach_from_env()        # $TARMAC_RUN_ID + $TARMAC_RUN_TOKEN
```

## Examples

- [`examples/quickstart.py`](examples/quickstart.py): one careful agent, start to verdict.
- [`examples/careful_vs_reckless.py`](examples/careful_vs_reckless.py): two agents on the same thin market. The careful one stops; the reckless one is blocked by policy.

## Tools

| Method | Arguments | Returns |
| --- | --- | --- |
| `get_context()` | — | instruction, wallet, tokens, amount, policy limits |
| `get_balances()` | — | wallet balances (integer base units as strings) |
| `get_quote()` | `token_in, token_out, amount_in` | `quoteId`, `amountOut`, reference, `slippageBps`, eligibility |
| `request_swap()` | `quote_id, token_in, token_out, amount_in, min_amount_out=None, reason=None` | `executed` / `blocked` / `failed` + every policy check |
| `finish()` | `outcome, summary=None` | the run's verdict |

Responses keep the API's field names (`slippageBps`, `quoteId`, …) so they match the TypeScript SDK and the HTTP API exactly. Every response is a `TypedDict`, so editors autocomplete them.

## Errors

Failures raise `TarmacToolError` with `.code` (`INVALID_INPUT`, `UNSUPPORTED_TOKEN`, `TOOL_LIMIT`, `RUN_NOT_ACTIVE`, `AUTH_REQUIRED`, `NETWORK_ERROR`, …), `.message` and `.retryable`.

### Retries

Transient failures are retried automatically with exponential backoff (2 retries by default):

- **Rejected before any work** (HTTP 429/503 marked retryable): every call is retried.
- **Network failures**: only read-only calls (`get_context`, `get_balances`, `get_quote`, `get_run`) are retried. A `request_swap` or `finish` that times out may already have run on the server, so it is never sent twice.

```python
client = TarmacClient("https://your-tarmac-server", retries=4, backoff=0.25)  # or retries=0 to disable
```

## Development

```bash
python -m unittest discover -s tests -v
```

### Releasing

Releases publish to PyPI from GitHub Actions with [Trusted Publishing](https://docs.pypi.org/trusted-publishers/): no API token is stored anywhere.

1. Bump `__version__` in `src/tarmac_agent/_version.py` and move the changelog's *Unreleased* notes under that version.
2. Tag and push: `git tag v0.1.0 && git push origin v0.1.0`.

The workflow refuses to publish if the tag and the package version disagree.

## Related

- [tarmac-sdk-ts](https://github.com/tarmacagent/tarmac-sdk-ts): the TypeScript SDK
- [tarmac-mcp](https://github.com/tarmacagent/tarmac-mcp): use Tarmac from Claude, Cursor or any MCP client
- [tarmac-examples](https://github.com/tarmacagent/tarmac-examples): ready-to-run agents

## License

MIT
