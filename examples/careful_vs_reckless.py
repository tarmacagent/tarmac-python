"""Two agents, one thin market: which one follows the rule?

Runs a careful agent (checks slippage first) and a reckless one (swaps no matter
what) against the same scenario, then prints both verdicts side by side.

    TARMAC_URL=http://localhost:3000 python examples/careful_vs_reckless.py

Expected on swap-thin: the careful agent stops, the reckless one is blocked by
policy. Nothing is ever broadcast; both runs use simulated funds.
"""

import os

from tarmac_agent import TarmacClient, TarmacTools, run_agent


def pair(ctx):
    return {"token_in": ctx["tokenIn"]["address"], "token_out": ctx["tokenOut"]["address"]}


def careful(tools: TarmacTools) -> None:
    ctx = tools.get_context()
    quote = tools.get_quote(**pair(ctx), amount_in=ctx["amountIn"])
    if quote["slippageBps"] > ctx["policy"]["maxSlippageBps"]:
        tools.finish("stopped", f"Slippage {quote['slippageBps']} bps is over the {ctx['policy']['maxSlippageBps']} bps limit.")
        return
    tools.request_swap(quote_id=quote["quoteId"], **pair(ctx), amount_in=ctx["amountIn"], reason="Within the slippage limit.")
    tools.finish("swapped")


def reckless(tools: TarmacTools) -> None:
    ctx = tools.get_context()
    quote = tools.get_quote(**pair(ctx), amount_in=ctx["amountIn"])
    # Never looks at slippage. Tarmac's policy checks still apply.
    tools.request_swap(quote_id=quote["quoteId"], **pair(ctx), amount_in=ctx["amountIn"], reason="Swap regardless.")
    tools.finish("swapped")


def main() -> None:
    client = TarmacClient.from_env()
    scenario = os.environ.get("SCENARIO", "swap-thin")
    rows = []
    for name, agent in (("careful", careful), ("reckless", reckless)):
        out = run_agent(client, agent, scenario=scenario, agent_name=f"python-{name}")
        result = out["run"].get("result") or {}
        rows.append((name, result.get("verdictLabel", out["run"]["status"]), out["session"].run_url))

    print(f"\nScenario: {scenario}\n")
    for name, verdict, url in rows:
        print(f"  {name:<9} {verdict}")
        print(f"  {'':<9} {url}\n")


if __name__ == "__main__":
    main()
