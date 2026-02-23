"""Unit tests for the TaskAdherenceEvaluator (orchestrator)."""

from agent_task_metering.evaluation.audit import AuditStore
from agent_task_metering.evaluation.contract import ContractConfig
from agent_task_metering.evaluation.evaluator import TaskAdherenceEvaluator
from agent_task_metering.evaluation.models import EvaluationRequest, Evidence

# ---- Acceptance criteria --------------------------------------------------


def test_passing_payload_adhered_billable():
    """Passing payload → intent_handled=True, adhered=True, billable_units=1."""
    evaluator = TaskAdherenceEvaluator()
    req = EvaluationRequest(
        task_id="t1",
        agent_id="a1",
        subscription_ref="sub-1",
        evidence=Evidence(outputs={"terminal_success": True, "result": "ok"}),
    )
    result = evaluator.evaluate(req)
    assert result.intent_handled is True
    assert result.adhered is True
    assert result.billable_units == 1
    assert result.correlation_id  # non-empty


def test_failing_payload_not_adhered_zero_units():
    """Failing payload → adhered=False, billable_units=0."""
    evaluator = TaskAdherenceEvaluator()
    req = EvaluationRequest(
        task_id="t2",
        agent_id="a1",
        subscription_ref="sub-1",
        evidence=Evidence(outputs={"status": "failed"}),
    )
    result = evaluator.evaluate(req)
    assert result.adhered is False
    assert result.billable_units == 0


def test_intent_not_handled_means_zero_units():
    """intent_handled=False + adhered=True → billable_units=0."""
    config = ContractConfig(require_intent_resolution=True)
    evaluator = TaskAdherenceEvaluator(config=config)
    req = EvaluationRequest(
        task_id="t-intent",
        agent_id="a1",
        subscription_ref="sub-1",
        evidence=Evidence(outputs={"terminal_success": True}),
    )
    result = evaluator.evaluate(req)
    assert result.intent_handled is False
    assert result.adhered is True
    assert result.billable_units == 0


def test_intent_handled_and_adhered_billable():
    """intent_handled=True + adhered=True → billable_units=1."""
    config = ContractConfig(require_intent_resolution=True)
    evaluator = TaskAdherenceEvaluator(config=config)
    req = EvaluationRequest(
        task_id="t-both",
        agent_id="a1",
        subscription_ref="sub-1",
        evidence=Evidence(
            outputs={"terminal_success": True, "intent_handled": True},
        ),
    )
    result = evaluator.evaluate(req)
    assert result.intent_handled is True
    assert result.adhered is True
    assert result.billable_units == 1


# ---- Audit trail ----------------------------------------------------------


def test_audit_record_persisted():
    """Every evaluation persists an audit record."""
    store = AuditStore()
    evaluator = TaskAdherenceEvaluator(audit_store=store)
    req = EvaluationRequest(
        task_id="t3",
        agent_id="a1",
        subscription_ref="sub-1",
        evidence=Evidence(outputs={"terminal_success": True}),
    )
    result = evaluator.evaluate(req)

    assert len(store) == 1
    audit = store.get(result.correlation_id)
    assert audit is not None
    assert audit.task_id == "t3"
    assert audit.intent_handled is True
    assert audit.adhered is True
    assert audit.billable_units == 1


def test_multiple_evaluations_each_have_audit():
    """Two evaluations produce two distinct audit records."""
    store = AuditStore()
    evaluator = TaskAdherenceEvaluator(audit_store=store)

    for i in range(2):
        req = EvaluationRequest(
            task_id=f"t{i}",
            agent_id="a1",
            subscription_ref="sub-1",
            evidence=Evidence(outputs={"terminal_success": True}),
        )
        evaluator.evaluate(req)

    assert len(store) == 2


def test_correlation_id_unique_per_call():
    """Each evaluation receives a unique correlation ID."""
    evaluator = TaskAdherenceEvaluator()
    ids = set()
    for i in range(5):
        req = EvaluationRequest(
            task_id=f"t{i}",
            agent_id="a1",
            subscription_ref="sub-1",
            evidence=Evidence(outputs={"terminal_success": True}),
        )
        result = evaluator.evaluate(req)
        ids.add(result.correlation_id)
    assert len(ids) == 5


def test_result_to_dict():
    """EvaluationResult.to_dict() contains all expected keys."""
    evaluator = TaskAdherenceEvaluator()
    req = EvaluationRequest(
        task_id="t1",
        agent_id="a1",
        subscription_ref="sub-1",
        evidence=Evidence(outputs={"terminal_success": True}),
    )
    d = evaluator.evaluate(req).to_dict()
    assert set(d.keys()) == {
        "intent_handled", "adhered", "billable_units", "reason_codes", "correlation_id",
    }
