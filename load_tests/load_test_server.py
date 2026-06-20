"""
load_test_server.py — Plain HTTP shim for K6 load testing
==========================================================
Wraps the MCP tool functions as standard JSON endpoints so K6
(which uses stateless HTTP) can hit them without the SSE session
handshake that the MCP SSE transport requires.

Runs on port 8010. Start before running K6:
  python load_tests/load_test_server.py

Endpoints:
  GET  /health
  POST /fraud/get_transaction_history
  POST /fraud/get_fraud_blacklist
  POST /fraud/get_fraud_statistics
  POST /fraud/report_fraud_transaction
  POST /geo/get_country_risk_score
  POST /geo/verify_domestic_location
  POST /geo/get_high_risk_regions
  POST /geo/check_ip_location
  POST /orch/get_system_status
  POST /orch/get_audit_trail
"""

import json
import sys
import os
import importlib.util
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _load_module(rel_path):
    full = os.path.join(ROOT, rel_path)
    spec = importlib.util.spec_from_file_location(rel_path.replace("/", "_").replace(".py",""), full)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_fraud = _load_module("mcp/mcp_server_fraud.py")
_geo   = _load_module("mcp/mcp_server_geo.py")
_orch  = _load_module("mcp/mcp_server_orchestrator.py")

PORT = 8010

ROUTES = {
    "/fraud/get_transaction_history":  _fraud.get_transaction_history,
    "/fraud/get_fraud_blacklist":       _fraud.get_fraud_blacklist,
    "/fraud/get_fraud_statistics":      _fraud.get_fraud_statistics,
    "/fraud/report_fraud_transaction":  _fraud.report_fraud_transaction,
    "/geo/get_country_risk_score":      _geo.get_country_risk_score,
    "/geo/verify_domestic_location":    _geo.verify_domestic_location,
    "/geo/get_high_risk_regions":       _geo.get_high_risk_regions,
    "/geo/check_ip_location":           _geo.check_ip_location,
    "/orch/get_system_status":          _orch.get_system_status,
    "/orch/get_audit_trail":            _orch.get_audit_trail,
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # suppress per-request noise

    def _send(self, code, body):
        data = json.dumps(body, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/health":
            self._send(200, {"status": "healthy", "port": PORT,
                              "routes": list(ROUTES.keys())})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        fn = ROUTES.get(self.path)
        if fn is None:
            self._send(404, {"error": f"unknown route: {self.path}"})
            return
        length = int(self.headers.get("Content-Length", 0))
        body   = json.loads(self.rfile.read(length)) if length > 0 else {}
        try:
            result = fn(**body) if body else fn()
            self._send(200, result)
        except TypeError as e:
            self._send(400, {"error": str(e)})
        except Exception as e:
            self._send(500, {"error": str(e)})


if __name__ == "__main__":
    print(f"Load test HTTP shim running on http://0.0.0.0:{PORT}")
    print(f"Routes: {list(ROUTES.keys())}")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
