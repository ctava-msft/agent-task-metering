"""Minimal REST API for task adherence evaluation.

Uses only the Python standard library (``http.server`` + ``json``) so that
no additional dependencies are required.  The server exposes:

* **POST /evaluate** — evaluate a task and return the billable outcome.
* **GET  /audit/<correlation_id>** — retrieve a single audit record.
* **GET  /health** — liveness probe (always returns 200).

Start with::

    python -m agent_task_metering.evaluation.api --port 8080
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional

from .contract import ContractConfig
from .evaluator import TaskAdherenceEvaluator
from .models import EvaluationRequest, Evidence

# Module-level evaluator (configured on server start).
_evaluator: Optional[TaskAdherenceEvaluator] = None


def _get_evaluator() -> TaskAdherenceEvaluator:
    global _evaluator  # noqa: PLW0603
    if _evaluator is None:
        _evaluator = TaskAdherenceEvaluator()
    return _evaluator


def configure(config: ContractConfig | None = None) -> TaskAdherenceEvaluator:
    """(Re)configure the module-level evaluator and return it."""
    global _evaluator  # noqa: PLW0603
    _evaluator = TaskAdherenceEvaluator(config=config)
    return _evaluator


# ------------------------------------------------------------------
# Request handler
# ------------------------------------------------------------------


class _Handler(BaseHTTPRequestHandler):
    """HTTP request handler for the evaluation API."""

    def _send_json(self, status: int, body: Dict[str, Any]) -> None:
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length)

    # --- POST /evaluate -----------------------------------------------

    def _handle_evaluate(self) -> None:
        try:
            raw = json.loads(self._read_body())
        except (json.JSONDecodeError, ValueError):
            self._send_json(400, {"error": "Invalid JSON"})
            return

        # Validate required fields
        missing = [f for f in ("task_id", "agent_id", "subscription_ref") if f not in raw]
        if missing:
            self._send_json(400, {"error": f"Missing fields: {', '.join(missing)}"})
            return

        evidence_raw = raw.get("evidence", {})
        evidence = Evidence(
            outputs=evidence_raw.get("outputs", {}),
            traces=evidence_raw.get("traces", []),
            scores=evidence_raw.get("scores", {}),
        )

        request = EvaluationRequest(
            task_id=raw["task_id"],
            agent_id=raw["agent_id"],
            subscription_ref=raw["subscription_ref"],
            evidence=evidence,
        )

        result = _get_evaluator().evaluate(request)
        self._send_json(200, result.to_dict())

    # --- GET /audit/<correlation_id> -----------------------------------

    def _handle_audit(self, correlation_id: str) -> None:
        audit = _get_evaluator().audit_store.get(correlation_id)
        if audit is None:
            self._send_json(404, {"error": "Audit record not found"})
            return
        self._send_json(200, audit.to_dict())

    # --- GET /health ---------------------------------------------------

    def _handle_health(self) -> None:
        self._send_json(200, {"status": "ok"})

    # --- Routing -------------------------------------------------------

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/evaluate":
            self._handle_evaluate()
        else:
            self._send_json(404, {"error": "Not found"})

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._handle_health()
        elif self.path.startswith("/audit/"):
            cid = self.path[len("/audit/"):]
            self._handle_audit(cid)
        else:
            self._send_json(404, {"error": "Not found"})

    # Suppress default stderr logging in tests
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        pass


def create_server(
    host: str = "0.0.0.0",
    port: int = 8080,
    config: ContractConfig | None = None,
) -> HTTPServer:
    """Create (but do not start) the evaluation HTTP server."""
    configure(config)
    return HTTPServer((host, port), _Handler)


# ------------------------------------------------------------------
# CLI entry-point
# ------------------------------------------------------------------


def main() -> None:  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser(description="Task adherence evaluation API")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    server = create_server(host=args.host, port=args.port)
    print(f"Serving on {args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
