"""Minimal REST API for task adherence evaluation.

Uses only the Python standard library (``http.server`` + ``json``) so that
no additional dependencies are required.  The server exposes:

* **POST /evaluate** — evaluate a task and return the billable outcome.
* **POST /evaluate_intent_handling** — evaluate intent resolution only.
* **POST /evaluate_task_adherence** — evaluate task adherence gates only.
* **POST /record_task_completed** — record a task completion for metering.
* **POST /evaluate_and_meter_task** — evaluate + meter in one call (recommended).
* **GET  /audit/<correlation_id>** — retrieve a single audit record.
* **GET  /health** — liveness probe (always returns 200).

Start with::

    python -m agent_task_metering.evaluation.api --port 8080
"""

from __future__ import annotations

import json
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional

from ..metering.client import MarketplaceMeteringClient
from .contract import ContractConfig, TaskAdherenceContract
from .evaluator import TaskAdherenceEvaluator
from .models import EvaluationRequest, Evidence

# Module-level evaluator (configured on server start).
_evaluator: Optional[TaskAdherenceEvaluator] = None
# Module-level metering client.
_metering_client: Optional[MarketplaceMeteringClient] = None


def _get_evaluator() -> TaskAdherenceEvaluator:
    global _evaluator  # noqa: PLW0603
    if _evaluator is None:
        _evaluator = TaskAdherenceEvaluator()
    return _evaluator


def _get_metering_client() -> MarketplaceMeteringClient:
    global _metering_client  # noqa: PLW0603
    if _metering_client is None:
        _metering_client = MarketplaceMeteringClient()
    return _metering_client


def configure(
    config: ContractConfig | None = None,
    metering_client: MarketplaceMeteringClient | None = None,
) -> TaskAdherenceEvaluator:
    """(Re)configure the module-level evaluator and metering client."""
    global _evaluator, _metering_client  # noqa: PLW0603
    _evaluator = TaskAdherenceEvaluator(config=config)
    if metering_client is not None:
        _metering_client = metering_client
    return _evaluator


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _parse_evidence(raw: Dict[str, Any]) -> Evidence:
    """Build an :class:`Evidence` from raw JSON dict."""
    evidence_raw = raw.get("evidence", {})
    return Evidence(
        outputs=evidence_raw.get("outputs", {}),
        traces=evidence_raw.get("traces", []),
        scores=evidence_raw.get("scores", {}),
        query=evidence_raw.get("query"),
        response=evidence_raw.get("response"),
    )


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

    def _read_json(self) -> Optional[Dict[str, Any]]:
        """Parse request body as JSON; send 400 on failure."""
        try:
            return json.loads(self._read_body())
        except (json.JSONDecodeError, ValueError):
            self._send_json(400, {"error": "Invalid JSON"})
            return None

    def _require_fields(self, raw: Dict[str, Any], fields: tuple) -> bool:
        """Validate required fields; send 400 on failure. Return True if ok."""
        missing = [f for f in fields if f not in raw]
        if missing:
            self._send_json(400, {"error": f"Missing fields: {', '.join(missing)}"})
            return False
        return True

    # --- POST /evaluate -----------------------------------------------

    def _handle_evaluate(self) -> None:
        raw = self._read_json()
        if raw is None:
            return
        if not self._require_fields(raw, ("task_id", "agent_id", "subscription_ref")):
            return

        evidence = _parse_evidence(raw)
        request = EvaluationRequest(
            task_id=raw["task_id"],
            agent_id=raw["agent_id"],
            subscription_ref=raw["subscription_ref"],
            evidence=evidence,
        )

        result = _get_evaluator().evaluate(request)
        self._send_json(200, result.to_dict())

    # --- POST /evaluate_intent_handling --------------------------------

    def _handle_evaluate_intent_handling(self) -> None:
        raw = self._read_json()
        if raw is None:
            return
        if not self._require_fields(raw, ("task_id", "agent_id", "subscription_ref")):
            return

        correlation_id = raw.get("correlation_id") or uuid.uuid4().hex
        evidence = _parse_evidence(raw)
        contract = TaskAdherenceContract(_get_evaluator()._contract._config)
        intent_handled, reason = contract._gate_intent_resolution(evidence)

        self._send_json(200, {
            "correlation_id": correlation_id,
            "intent_handled": intent_handled,
            "reason": reason,
        })

    # --- POST /evaluate_task_adherence ---------------------------------

    def _handle_evaluate_task_adherence(self) -> None:
        raw = self._read_json()
        if raw is None:
            return
        if not self._require_fields(raw, ("task_id", "agent_id", "subscription_ref")):
            return

        correlation_id = raw.get("correlation_id") or uuid.uuid4().hex
        evidence = _parse_evidence(raw)
        contract = TaskAdherenceContract(_get_evaluator()._contract._config)

        outputs = evidence.outputs
        gates = [
            contract._gate_terminal_success(outputs),
            contract._gate_required_outputs(outputs),
            contract._gate_output_validation(outputs),
            contract._gate_approval(outputs),
        ]
        adhered = all(passed for passed, _ in gates)
        reason_codes = [code for _, code in gates]

        self._send_json(200, {
            "correlation_id": correlation_id,
            "adhered": adhered,
            "reason_codes": reason_codes,
        })

    # --- POST /record_task_completed -----------------------------------

    def _handle_record_task_completed(self) -> None:
        raw = self._read_json()
        if raw is None:
            return
        if not self._require_fields(raw, ("task_id", "subscription_ref")):
            return

        correlation_id = raw.get("correlation_id") or uuid.uuid4().hex
        client = _get_metering_client()
        newly_recorded = client.record_task_completed(
            subscription_ref=raw["subscription_ref"],
            task_id=raw["task_id"],
        )

        self._send_json(200, {
            "correlation_id": correlation_id,
            "recorded": newly_recorded,
        })

    # --- POST /evaluate_and_meter_task ---------------------------------

    def _handle_evaluate_and_meter_task(self) -> None:
        raw = self._read_json()
        if raw is None:
            return
        if not self._require_fields(raw, ("task_id", "agent_id", "subscription_ref")):
            return

        evidence = _parse_evidence(raw)
        request = EvaluationRequest(
            task_id=raw["task_id"],
            agent_id=raw["agent_id"],
            subscription_ref=raw["subscription_ref"],
            evidence=evidence,
        )

        result = _get_evaluator().evaluate(request)
        correlation_id = raw.get("correlation_id") or result.correlation_id

        # Record metering when billable
        recorded = False
        if result.billable_units > 0:
            client = _get_metering_client()
            recorded = client.record_task_completed(
                subscription_ref=raw["subscription_ref"],
                task_id=raw["task_id"],
            )

        body = result.to_dict()
        body["correlation_id"] = correlation_id
        body["recorded"] = recorded
        self._send_json(200, body)

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

    _POST_ROUTES: Dict[str, str] = {
        "/evaluate": "_handle_evaluate",
        "/evaluate_intent_handling": "_handle_evaluate_intent_handling",
        "/evaluate_task_adherence": "_handle_evaluate_task_adherence",
        "/record_task_completed": "_handle_record_task_completed",
        "/evaluate_and_meter_task": "_handle_evaluate_and_meter_task",
    }

    def do_POST(self) -> None:  # noqa: N802
        handler_name = self._POST_ROUTES.get(self.path)
        if handler_name:
            getattr(self, handler_name)()
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
    metering_client: MarketplaceMeteringClient | None = None,
) -> HTTPServer:
    """Create (but do not start) the evaluation HTTP server."""
    configure(config, metering_client=metering_client)
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
