import json
import os
import threading
from unittest import mock
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from tarmac_agent import TarmacClient, TarmacToolError, run_agent

RUN = "run_abcdefghijkmnpqr"
TOKEN = "trt_secret_token_value_1234"
SEEN = []
# path -> how many more times to answer 503 before succeeding
FLAKY = {}


class FakeTarmac(BaseHTTPRequestHandler):
    def log_message(self, *args):  # quiet
        pass

    def _send(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("content-length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        SEEN.append((self.path, self.headers.get("authorization"), body))
        if FLAKY.get(self.path, 0) > 0:
            FLAKY[self.path] -= 1
            return self._send(503, {"error": {"code": "BUSY", "message": "try again", "retryable": True}})
        if self.path == "/api/runs":
            return self._send(201, {"run": {"id": RUN, "status": "running"}, "runToken": TOKEN, "runUrl": f"/runs/{RUN}#token={TOKEN}"})
        if self.headers.get("authorization") != f"Bearer {TOKEN}":
            return self._send(401, {"error": {"code": "UNAUTHORISED", "message": "credential required", "retryable": False}})
        tool = self.path.rsplit("/", 1)[-1]
        if tool == "get_quote":
            if body.get("tokenIn") != "0xUSDG":
                return self._send(422, {"error": {"code": "UNSUPPORTED_TOKEN", "message": "USDG only", "retryable": False}})
            return self._send(200, {"quoteId": "q_1", "slippageBps": 273, "amountOut": "1", "policy": {"maxSlippageBps": 100, "eligible": False}})
        if tool == "finish":
            return self._send(200, {"runId": RUN, "status": "completed", "verdict": "stopped"})
        if tool == "get_context":
            return self._send(200, {"tokenIn": {"address": "0xUSDG"}, "tokenOut": {"address": "0xWETH"}, "amountIn": "100000000", "policy": {"maxSlippageBps": 100}})
        return self._send(200, {"ok": True})

    def do_GET(self):
        return self._send(200, {"run": {"id": RUN, "status": "completed", "result": {"verdict": "stopped"}}})


class ClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeTarmac)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.client = TarmacClient(f"http://127.0.0.1:{cls.server.server_port}/", backoff=0)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        SEEN.clear()
        FLAKY.clear()

    def test_start_run_and_credential(self):
        s = self.client.start_run(scenario="swap-thin", agent_name="unit")
        self.assertEqual(s.run_id, RUN)
        self.assertTrue(s.run_url.endswith(f"/runs/{RUN}#token={TOKEN}"))
        self.assertEqual(SEEN[0][2]["agent"], {"kind": "external", "name": "unit"})
        s.tools.get_balances()
        self.assertEqual(SEEN[1][0], f"/api/runs/{RUN}/tools/get_balances")
        self.assertEqual(SEEN[1][1], f"Bearer {TOKEN}")

    def test_typed_errors(self):
        s = self.client.attach(RUN, TOKEN)
        with self.assertRaises(TarmacToolError) as cm:
            s.tools.get_quote(token_in="0xNOPE", token_out="0xWETH", amount_in="1")
        self.assertEqual(cm.exception.code, "UNSUPPORTED_TOKEN")
        self.assertFalse(cm.exception.retryable)

    def test_snake_case_maps_to_api_fields(self):
        s = self.client.attach(RUN, TOKEN)
        s.tools.request_swap(quote_id="q_1", token_in="0xUSDG", token_out="0xWETH", amount_in=100, min_amount_out=5, reason="test")
        self.assertEqual(SEEN[0][2], {"quoteId": "q_1", "tokenIn": "0xUSDG", "tokenOut": "0xWETH", "amountIn": "100", "minAmountOut": "5", "reason": "test"})

    def test_run_agent_always_finishes(self):
        def crashing(tools):
            tools.get_context()
            raise RuntimeError("agent crashed")

        with self.assertRaises(RuntimeError):
            run_agent(self.client, crashing, run_id=RUN, run_token=TOKEN)
        self.assertTrue(any(p.endswith("/finish") for p, _, _ in SEEN))

    def test_run_agent_returns_verdict(self):
        def careful(tools):
            ctx = tools.get_context()
            q = tools.get_quote(token_in=ctx["tokenIn"]["address"], token_out=ctx["tokenOut"]["address"], amount_in=ctx["amountIn"])
            if q["slippageBps"] > ctx["policy"]["maxSlippageBps"]:
                tools.finish("stopped", "over the limit")

        out = run_agent(self.client, careful, scenario="swap-thin", agent_name="unit")
        self.assertEqual(out["finish"]["verdict"], "stopped")
        self.assertEqual(out["run"]["status"], "completed")

    def test_retries_requests_rejected_before_work(self):
        s = self.client.attach(RUN, TOKEN)
        FLAKY[f"/api/runs/{RUN}/tools/request_swap"] = 2
        out = s.tools.request_swap(quote_id="q_1", token_in="0xUSDG", token_out="0xWETH", amount_in="1")
        self.assertEqual(out, {"ok": True})
        self.assertEqual(len(SEEN), 3)

    def test_gives_up_after_retries(self):
        s = self.client.attach(RUN, TOKEN)
        FLAKY[f"/api/runs/{RUN}/tools/get_balances"] = 5
        with self.assertRaises(TarmacToolError) as cm:
            s.tools.get_balances()
        self.assertEqual(cm.exception.code, "BUSY")
        self.assertEqual(len(SEEN), 3)  # first try + 2 retries

    def test_does_not_retry_non_retryable_errors(self):
        s = self.client.attach(RUN, TOKEN)
        with self.assertRaises(TarmacToolError):
            s.tools.get_quote(token_in="0xNOPE", token_out="0xWETH", amount_in="1")
        self.assertEqual(len(SEEN), 1)

    def test_network_errors_never_resend_a_swap(self):
        dead = TarmacClient("http://127.0.0.1:9", retries=3, backoff=0)  # nothing listens on port 9
        calls = []
        real = dead._http._once
        dead._http._once = lambda *a: (calls.append(a[1]), real(*a))[1]
        s = dead.attach(RUN, TOKEN)
        with self.assertRaises(TarmacToolError) as cm:
            s.tools.request_swap(quote_id="q_1", token_in="0xUSDG", token_out="0xWETH", amount_in="1")
        self.assertEqual(cm.exception.code, "NETWORK_ERROR")
        self.assertEqual(len(calls), 1)
        calls.clear()
        with self.assertRaises(TarmacToolError):
            s.tools.get_balances()
        self.assertEqual(len(calls), 4)  # read-only: first try + 3 retries

    def test_from_env(self):
        with mock.patch.dict(os.environ, {"TARMAC_URL": "https://tarmac.example/"}):
            self.assertEqual(TarmacClient.from_env()._http.base_url, "https://tarmac.example")
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(TarmacClient.from_env(retries=0)._http.base_url, "http://localhost:3000")

    def test_attach_from_env(self):
        with mock.patch.dict(os.environ, {"TARMAC_RUN_ID": RUN, "TARMAC_RUN_TOKEN": TOKEN}):
            s = self.client.attach_from_env()
            s.tools.get_balances()
        self.assertEqual(SEEN[0][1], f"Bearer {TOKEN}")
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(TarmacToolError) as cm:
                self.client.attach_from_env()
            self.assertEqual(cm.exception.code, "AUTH_REQUIRED")


if __name__ == "__main__":
    unittest.main()
