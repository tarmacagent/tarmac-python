from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from ._errors import TarmacToolError
from ._types import BalancesResult, FinishResult, QuoteResult, RunContext, SwapResult

_USER_AGENT = "tarmac-agent-python/0.1.0"


class _Http:
    def __init__(self, base_url: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def request(self, method: str, path: str, body: Any = None, token: Optional[str] = None) -> Any:
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.base_url + path, data=data, method=method)
        req.add_header("accept", "application/json")
        req.add_header("user-agent", _USER_AGENT)
        if data is not None:
            req.add_header("content-type", "application/json")
        if token:
            req.add_header("authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as res:
                return json.loads(res.read() or b"null")
        except urllib.error.HTTPError as e:
            payload: Dict[str, Any] = {}
            try:
                payload = json.loads(e.read() or b"{}")
            except ValueError:
                pass
            err = payload.get("error") or {}
            raise TarmacToolError(err.get("code") or f"HTTP_{e.code}", err.get("message") or e.reason, bool(err.get("retryable"))) from None
        except urllib.error.URLError as e:
            raise TarmacToolError("NETWORK_ERROR", str(e.reason), True) from None


class TarmacTools:
    """The five tools an agent can call. Same contract as the TypeScript SDK."""

    def __init__(self, http: _Http, run_id: str, token: str) -> None:
        self._http, self._run_id, self._token = http, run_id, token

    def _call(self, tool: str, payload: Optional[Dict[str, Any]] = None) -> Any:
        return self._http.request("POST", f"/api/runs/{self._run_id}/tools/{tool}", payload or {}, self._token)

    def get_context(self) -> RunContext:
        return self._call("get_context")

    def get_balances(self) -> BalancesResult:
        return self._call("get_balances")

    def get_quote(self, *, token_in: str, token_out: str, amount_in: str) -> QuoteResult:
        return self._call("get_quote", {"tokenIn": token_in, "tokenOut": token_out, "amountIn": str(amount_in)})

    def request_swap(
        self,
        *,
        quote_id: str,
        token_in: str,
        token_out: str,
        amount_in: str,
        min_amount_out: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> SwapResult:
        body: Dict[str, Any] = {"quoteId": quote_id, "tokenIn": token_in, "tokenOut": token_out, "amountIn": str(amount_in)}
        if min_amount_out is not None:
            body["minAmountOut"] = str(min_amount_out)
        if reason is not None:
            body["reason"] = reason
        return self._call("request_swap", body)

    def finish(self, outcome: str, summary: Optional[str] = None) -> FinishResult:
        body: Dict[str, Any] = {"outcome": outcome}
        if summary is not None:
            body["summary"] = summary
        return self._call("finish", body)


@dataclass
class RunSession:
    run_id: str
    run_token: str
    run_url: str
    tools: TarmacTools
    _http: _Http

    def get_run(self) -> Dict[str, Any]:
        """The current run record: status, verdict, trace."""
        return self._http.request("GET", f"/api/runs/{self.run_id}", token=self.run_token)["run"]


class TarmacClient:
    """Client for a Tarmac server.

    >>> client = TarmacClient("http://localhost:3000")
    >>> session = client.start_run(scenario="swap-thin", agent_name="my-agent")
    """

    def __init__(self, base_url: str, timeout: float = 120.0) -> None:
        self._http = _Http(base_url, timeout)

    def start_run(
        self,
        *,
        scenario: str,
        agent_name: str,
        token: str = "WETH",
        mode: str = "fixture",
        policy: Optional[Dict[str, int]] = None,
    ) -> RunSession:
        created = self._http.request(
            "POST",
            "/api/runs",
            {"scenarioId": scenario, "token": token, "mode": mode, "agent": {"kind": "external", "name": agent_name}, "policy": policy or {}},
        )
        return RunSession(created["run"]["id"], created["runToken"], self._http.base_url + created["runUrl"], TarmacTools(self._http, created["run"]["id"], created["runToken"]), self._http)

    def attach(self, run_id: str, run_token: str) -> RunSession:
        """Attach to a run created elsewhere (e.g. "Your agent" in the Tarmac app)."""
        return RunSession(run_id, run_token, f"{self._http.base_url}/runs/{run_id}#token={run_token}", TarmacTools(self._http, run_id, run_token), self._http)


def run_agent(
    client: TarmacClient,
    agent: Callable[[TarmacTools], None],
    *,
    run_id: Optional[str] = None,
    run_token: Optional[str] = None,
    **start: Any,
) -> Dict[str, Any]:
    """Start (or attach to) a run, hand the tools to ``agent``, and always finish the run.

    Returns ``{"session": RunSession, "run": dict, "finish": dict | None}``.
    """
    session = client.attach(run_id, run_token) if run_id and run_token else client.start_run(**start)
    finished: Dict[str, Any] = {}
    real_finish = session.tools.finish

    def finish(outcome: str, summary: Optional[str] = None) -> FinishResult:
        result = real_finish(outcome, summary)
        finished["result"] = result
        return result

    session.tools.finish = finish  # type: ignore[method-assign]
    try:
        agent(session.tools)
    finally:
        if "result" not in finished:
            try:
                finish("stopped", "Agent returned without calling finish.")
            except TarmacToolError:
                pass
    return {"session": session, "run": session.get_run(), "finish": finished.get("result")}
