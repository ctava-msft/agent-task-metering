"""Tests for the new MCP / OpenAPI endpoints."""

import json
import threading
from http.client import HTTPConnection

import pytest

from agent_task_metering.evaluation.api import create_server
from agent_task_metering.metering.client import MarketplaceMeteringClient


@pytest.fixture()
def metering_client():
    return MarketplaceMeteringClient(dry_run=True)


@pytest.fixture()
def server(metering_client):
    """Start the API with a shared metering client on a random port."""
    srv = create_server(host="127.0.0.1", port=0, metering_client=metering_client)
    _, port = srv.server_address
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield port, metering_client
    srv.shutdown()


def _post_json(port: int, path: str, body: dict) -> tuple:
    conn = HTTPConnection("127.0.0.1", port)
    payload = json.dumps(body).encode()
    conn.request("POST", path, body=payload, headers={"Content-Type": "application/json"})
    resp = conn.getresponse()
    data = json.loads(resp.read())
    status = resp.status
    conn.close()
    return status, data


# ---- POST /evaluate_intent_handling --------------------------------------


def test_evaluate_intent_handling_passed(server):
    port, _ = server
    status, body = _post_json(port, "/evaluate_intent_handling", {
        "task_id": "t1",
        "agent_id": "a1",
        "subscription_ref": "sub-1",
        "evidence": {"query": "What time?", "response": "9 AM"},
    })
    assert status == 200
    assert body["intent_handled"] is True
    assert "correlation_id" in body
    assert "reason" in body


def test_evaluate_intent_handling_with_caller_correlation_id(server):
    port, _ = server
    status, body = _post_json(port, "/evaluate_intent_handling", {
        "task_id": "t1",
        "agent_id": "a1",
        "subscription_ref": "sub-1",
        "correlation_id": "my-custom-id",
        "evidence": {"query": "What time?", "response": "9 AM"},
    })
    assert status == 200
    assert body["correlation_id"] == "my-custom-id"


def test_evaluate_intent_handling_missing_fields(server):
    port, _ = server
    status, body = _post_json(port, "/evaluate_intent_handling", {"task_id": "t1"})
    assert status == 400
    assert "Missing fields" in body["error"]


# ---- POST /evaluate_task_adherence ----------------------------------------


def test_evaluate_task_adherence_passed(server):
    port, _ = server
    status, body = _post_json(port, "/evaluate_task_adherence", {
        "task_id": "t1",
        "agent_id": "a1",
        "subscription_ref": "sub-1",
        "evidence": {"outputs": {"terminal_success": True, "result": "ok"}},
    })
    assert status == 200
    assert body["adhered"] is True
    assert "correlation_id" in body
    assert isinstance(body["reason_codes"], list)


def test_evaluate_task_adherence_failed(server):
    port, _ = server
    status, body = _post_json(port, "/evaluate_task_adherence", {
        "task_id": "t1",
        "agent_id": "a1",
        "subscription_ref": "sub-1",
        "evidence": {"outputs": {"status": "failed"}},
    })
    assert status == 200
    assert body["adhered"] is False


# ---- POST /record_task_completed -----------------------------------------


def test_record_task_completed(server):
    port, client = server
    status, body = _post_json(port, "/record_task_completed", {
        "task_id": "t-record",
        "subscription_ref": "sub-1",
    })
    assert status == 200
    assert body["recorded"] is True
    assert "correlation_id" in body


def test_record_task_completed_duplicate(server):
    port, _ = server
    _post_json(port, "/record_task_completed", {
        "task_id": "t-dup",
        "subscription_ref": "sub-1",
    })
    status, body = _post_json(port, "/record_task_completed", {
        "task_id": "t-dup",
        "subscription_ref": "sub-1",
    })
    assert status == 200
    assert body["recorded"] is False


def test_record_task_completed_missing_fields(server):
    port, _ = server
    status, body = _post_json(port, "/record_task_completed", {"task_id": "t1"})
    assert status == 400
    assert "Missing fields" in body["error"]


# ---- POST /evaluate_and_meter_task (recommended) -------------------------


def test_evaluate_and_meter_task_billable(server):
    """Passing evidence → billable_units=1 and recorded=True."""
    port, _ = server
    status, body = _post_json(port, "/evaluate_and_meter_task", {
        "task_id": "t-meter",
        "agent_id": "a1",
        "subscription_ref": "sub-1",
        "evidence": {
            "outputs": {"terminal_success": True, "result": "ok"},
        },
    })
    assert status == 200
    assert body["intent_handled"] is True
    assert body["adhered"] is True
    assert body["billable_units"] == 1
    assert body["recorded"] is True
    assert "correlation_id" in body


def test_evaluate_and_meter_task_not_billable(server):
    """Failing evidence → billable_units=0 and recorded=False."""
    port, _ = server
    status, body = _post_json(port, "/evaluate_and_meter_task", {
        "task_id": "t-no-meter",
        "agent_id": "a1",
        "subscription_ref": "sub-1",
        "evidence": {"outputs": {"status": "failed"}},
    })
    assert status == 200
    assert body["billable_units"] == 0
    assert body["recorded"] is False


def test_evaluate_and_meter_task_with_correlation_id(server):
    """Caller-supplied correlation_id is returned."""
    port, _ = server
    status, body = _post_json(port, "/evaluate_and_meter_task", {
        "task_id": "t-corr",
        "agent_id": "a1",
        "subscription_ref": "sub-1",
        "correlation_id": "caller-cid-123",
        "evidence": {
            "outputs": {"terminal_success": True, "result": "ok"},
        },
    })
    assert status == 200
    assert body["correlation_id"] == "caller-cid-123"


def test_evaluate_and_meter_task_missing_fields(server):
    port, _ = server
    status, body = _post_json(port, "/evaluate_and_meter_task", {"task_id": "t1"})
    assert status == 400
    assert "Missing fields" in body["error"]
