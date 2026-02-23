"""Unit tests for evaluation models."""

from agent_task_metering.evaluation.models import (
    AuditRecord,
    EvaluationRequest,
    EvaluationResult,
    Evidence,
)


def test_evidence_defaults():
    ev = Evidence()
    assert ev.outputs == {}
    assert ev.traces == []
    assert ev.scores == {}


def test_evidence_with_data():
    ev = Evidence(
        outputs={"status": "completed"},
        traces=[{"step": 1}],
        scores={"quality": 0.9},
    )
    assert ev.outputs["status"] == "completed"
    assert len(ev.traces) == 1
    assert ev.scores["quality"] == 0.9


def test_evaluation_request_fields():
    req = EvaluationRequest(
        task_id="t1",
        agent_id="a1",
        subscription_ref="sub-1",
        evidence=Evidence(outputs={"status": "completed"}),
    )
    assert req.task_id == "t1"
    assert req.agent_id == "a1"
    assert req.subscription_ref == "sub-1"
    assert req.evidence.outputs["status"] == "completed"


def test_evaluation_request_default_evidence():
    req = EvaluationRequest(task_id="t1", agent_id="a1", subscription_ref="sub-1")
    assert req.evidence.outputs == {}


def test_evaluation_result_to_dict():
    result = EvaluationResult(
        adhered=True,
        billable_units=1,
        reason_codes=["terminal_success:passed"],
        correlation_id="abc123",
    )
    d = result.to_dict()
    assert d["adhered"] is True
    assert d["billable_units"] == 1
    assert d["correlation_id"] == "abc123"
    assert "terminal_success:passed" in d["reason_codes"]


def test_audit_record_to_dict():
    audit = AuditRecord(
        correlation_id="abc123",
        task_id="t1",
        agent_id="a1",
        subscription_ref="sub-1",
        evidence={"outputs": {"status": "completed"}},
        adhered=True,
        billable_units=1,
        reason_codes=["terminal_success:passed"],
    )
    d = audit.to_dict()
    assert d["correlation_id"] == "abc123"
    assert d["task_id"] == "t1"
    assert "timestamp" in d
    # timestamp is serialised as ISO string
    assert isinstance(d["timestamp"], str)


def test_audit_record_default_metadata():
    audit = AuditRecord(
        correlation_id="x",
        task_id="t1",
        agent_id="a1",
        subscription_ref="sub-1",
        evidence={},
        adhered=False,
        billable_units=0,
        reason_codes=[],
    )
    assert audit.metadata is None
