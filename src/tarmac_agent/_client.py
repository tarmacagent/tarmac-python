from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from ._errors import TarmacToolError
from ._types import BalancesResult, FinishResult, QuoteResult, RunContext, SwapResult

_USER_AGENT = "tarmac-agent-python/0.1.0"


# Statuses the server uses when it rejected a request before doing any work.
_REJECTED_BEFORE_WORK = {429, 503}
# Tools that only read state: safe to repeat if a response was lost in transit.
_READ_ONLY_TOOLS = {"get_context", "get_balances", "get_quote"}


class _Http:
    def __init__(self, base_url: str, timeout: float, retries: int = 2, backoff: float = 0.5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = max(0, retries)
        self.backoff = max(0.0, backoff)

    def request(self, method: str, path: str, body: Any = None, token: Optional[str] = None, *, idempotent: bool = False) -> Any:
        """Send a request, retrying transient failures.

        A request the server *rejected before doing any work* (429/503 marked retryable) is
        always safe to retry. A network failure is retried only for ``idempotent`` requests:
        if a swap request times out, it may already have run, so it is never sent twice.
        """
        attempt = 0
        while True:
            try:
                return self._once(method, path, body, token)
            except _Retryable as r:
                if attempt >= self.retries or (r.network and not idempotent):
                    raise r.error from None
                time.sleep(self.backoff * (2**attempt))
                attempt += 1

    def _once(self, method: str, path: str, body: Any, token: Optional[str]) -> Any:
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
            error = TarmacToolError(err.get("code") or f"HTTP_{e.code}", err.get("message") or e.reason, bool(err.get("retryable")))
            if e.code in _REJECTED_BEFORE_WORK and error.retryable:
                raise _Retryable(error, network=False) from None
            raise error from None
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            reason = getattr(e, "reason", e)
            raise _Retryable(TarmacToolError("NETWORK_ERROR", str(reason), True), network=True) from None


class _Retryable(Exception):
    def __init__(self, error: TarmacToolError, network: bool) -> None:
        super().__init__(str(error))
        self.error = error
        self.network = network


class TarmacTools:
    """The five tools an agent can call. Same contract as the TypeScript SDK."""

    def __init__(self, http: _Http, run_id: str, token: str) -> None:
        self._http, self._run_id, self._token = http, run_id, token

    def _call(self, tool: str, payload: Optional[Dict[str, Any]] = None) -> Any:
        return self._http.request("POST", f"/api/runs/{self._run_id}/tools/{tool}", payload or {}, self._token, idempotent=tool in _READ_ONLY_TOOLS)

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
        return self._http.request("GET", f"/api/runs/{self.run_id}", token=self.run_token, idempotent=True)["run"]


class TarmacClient:
    """Client for a Tarmac server.

    >>> client = TarmacClient("http://localhost:3000")
    >>> session = client.start_run(scenario="swap-thin", agent_name="my-agent")

    ``retries`` and ``backoff`` control how transient failures are retried (exponential:
    0.5s, 1s, ...). Swap requests are never re-sent after a network failure.
    """

    def __init__(self, base_url: str, timeout: float = 120.0, *, retries: int = 2, backoff: float = 0.5) -> None:
        self._http = _Http(base_url, timeout, retries, backoff)

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

    @classmethod
    def from_env(cls, **options: Any) -> "TarmacClient":
        """Client for ``$TARMAC_URL`` (default ``http://localhost:3000``). Extra options go to ``__init__``."""
        return cls(os.environ.get("TARMAC_URL") or "http://localhost:3000", **options)

    def attach_from_env(self) -> RunSession:
        """Attach using ``$TARMAC_RUN_ID`` and ``$TARMAC_RUN_TOKEN`` (from "Your agent" in the Tarmac app)."""
        run_id, run_token = os.environ.get("TARMAC_RUN_ID"), os.environ.get("TARMAC_RUN_TOKEN")
        if not run_id or not run_token:
            raise TarmacToolError("AUTH_REQUIRED", "Set TARMAC_RUN_ID and TARMAC_RUN_TOKEN (create the run in the app with \"Your agent\").")
        return self.attach(run_id, run_token)

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
