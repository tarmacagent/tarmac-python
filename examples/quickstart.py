"""Run a careful agent against a Tarmac server.

    TARMAC_URL=http://localhost:3000 SCENARIO=swap-thin python examples/quickstart.py

If the server requires sign-in, create the run in the app ("Your agent") and set
TARMAC_RUN_ID and TARMAC_RUN_TOKEN instead.
"""

import os

from tarmac_agent import TarmacClient, TarmacTools, run_agent


def my_agent(tools: TarmacTools) -> None:
    ctx = tools.get_context()
    print("Instruction:", ctx["instruction"])
    quote = tools.get_quote(token_in=ctx["tokenIn"]["address"], token_out=ctx["tokenOut"]["address"], amount_in=ctx["amountIn"])
    print(f"Quote: slippage {quote['slippageBps']} bps (limit {ctx['policy']['maxSlippageBps']})")
    if quote["slippageBps"] > ctx["policy"]["maxSlippageBps"]:
        tools.finish("stopped", "Slippage over the limit.")
        return
    swap = tools.request_swap(quote_id=quote["quoteId"], token_in=ctx["tokenIn"]["address"], token_out=ctx["tokenOut"]["address"], amount_in=ctx["amountIn"])
    print("Swap:", swap["status"])
    tools.finish("swapped" if swap["status"] == "executed" else "stopped")


client = TarmacClient.from_env()
if os.environ.get("TARMAC_RUN_ID") and os.environ.get("TARMAC_RUN_TOKEN"):
    out = run_agent(client, my_agent, run_id=os.environ["TARMAC_RUN_ID"], run_token=os.environ["TARMAC_RUN_TOKEN"])
else:
    out = run_agent(client, my_agent, scenario=os.environ.get("SCENARIO", "swap-normal"), token=os.environ.get("TOKEN", "WETH"), agent_name="python-quickstart")

result = out["run"].get("result") or {}
print("\nVerdict:", result.get("verdictLabel", out["run"]["status"]))
print("Reason: ", result.get("reason", ""))
print("Trace:  ", out["session"].run_url)
