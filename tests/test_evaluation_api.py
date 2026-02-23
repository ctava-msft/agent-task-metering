"""Unit tests for the evaluation REST API."""

import json
import threading
from http.client import HTTPConnection

import pytest

from agent_task_metering.evaluation.api import create_server


@pytest.fixture()
def server():
    """Start the API on a random free port and tear down after the test."""
    srv = create_server(host="127.0.0.1", port=0)  # port 0 → OS picks free port
    _, port = srv.server_address
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield port
    srv.shutdown()


def _post_json(port: int, path: str, body: dict) -> tuple:
    """Helper: POST JSON and return (status, parsed_body)."""
    conn = HTTPConnection("127.0.0.1", port)
    payload = json.dumps(body).encode()
    conn.request("POST", path, body=payload, headers={"Content-Type": "application/json"})
    resp = conn.getresponse()
    data = json.loads(resp.read())
    status = resp.status
    conn.close()
    return status, data


def _get_json(port: int, path: str) -> tuple:
    """Helper: GET and return (status, parsed_body)."""
    conn = HTTPConnection("127.0.0.1", port)
    conn.request("GET", path)
    resp = conn.getresponse()
    data = json.loads(resp.read())
    status = resp.status
    conn.close()
    return status, data


# ---- POST /evaluate ------------------------------------------------------


def test_evaluate_passing_payload(server):
    """Passing evidence → adhered=True, billable_units=1."""
    status, body = _post_json(server, "/evaluate", {
        "task_id": "t1",
        "agent_id": "a1",
        "subscription_ref": "sub-1",
        "evidence": {
            "outputs": {"terminal_success": True, "result": "ok"},
            "traces": [{"step": 1}],
        },
    })
    assert status == 200
    assert body["adhered"] is True
    assert body["billable_units"] == 1
    assert body["correlation_id"]
    assert isinstance(body["reason_codes"], list)


def test_evaluate_failing_payload(server):
    """Failing evidence → adhered=False, billable_units=0."""
    status, body = _post_json(server, "/evaluate", {
        "task_id": "t2",
        "agent_id": "a1",
        "subscription_ref": "sub-1",
        "evidence": {"outputs": {"status": "failed"}},
    })
    assert status == 200
    assert body["adhered"] is False
    assert body["billable_units"] == 0


def test_evaluate_missing_fields(server):
    """Missing required fields → 400 error."""
    status, body = _post_json(server, "/evaluate", {"task_id": "t1"})
    assert status == 400
    assert "Missing fields" in body["error"]


def test_evaluate_invalid_json(server):
    """Malformed JSON → 400 error."""
    conn = HTTPConnection("127.0.0.1", server)
    conn.request("POST", "/evaluate", body=b"not-json", headers={"Content-Type": "text/plain"})
    resp = conn.getresponse()
    assert resp.status == 400
    conn.close()


def test_evaluate_minimal_evidence(server):
    """Evidence with empty outputs → adhered=False."""
    status, body = _post_json(server, "/evaluate", {
        "task_id": "t3",
        "agent_id": "a1",
        "subscription_ref": "sub-1",
    })
    assert status == 200
    assert body["adhered"] is False
    assert body["billable_units"] == 0


# ---- GET /audit/<correlation_id> -----------------------------------------


def test_audit_record_retrievable(server):
    """After evaluation, the audit record is retrievable by correlation ID."""
    _, eval_body = _post_json(server, "/evaluate", {
        "task_id": "t-audit",
        "agent_id": "a1",
        "subscription_ref": "sub-1",
        "evidence": {"outputs": {"terminal_success": True}},
    })
    cid = eval_body["correlation_id"]

    status, audit = _get_json(server, f"/audit/{cid}")
    assert status == 200
    assert audit["correlation_id"] == cid
    assert audit["task_id"] == "t-audit"
    assert audit["adhered"] is True


def test_audit_not_found(server):
    """Unknown correlation ID → 404."""
    status, body = _get_json(server, "/audit/nonexistent")
    assert status == 404


# ---- GET /health ----------------------------------------------------------


def test_health_endpoint(server):
    status, body = _get_json(server, "/health")
    assert status == 200
    assert body["status"] == "ok"


# ---- 404 for unknown routes -----------------------------------------------


def test_unknown_post_route(server):
    status, body = _post_json(server, "/unknown", {})
    assert status == 404


def test_unknown_get_route(server):
    status, body = _get_json(server, "/unknown")
    assert status == 404
