"""Unit tests for the TaskAdherenceContract."""

from agent_task_metering.evaluation.contract import ContractConfig, TaskAdherenceContract
from agent_task_metering.evaluation.models import Evidence

# ---- Intent resolution gate -----------------------------------------------


def test_intent_resolution_skipped_by_default():
    """When require_intent_resolution=False, gate 0 is skipped."""
    contract = TaskAdherenceContract()
    evidence = Evidence(outputs={"terminal_success": True})
    intent_handled, _, codes = contract.evaluate(evidence)
    assert intent_handled is True
    assert "intent_resolution:skipped" in codes


def test_intent_resolution_passes_with_score():
    """scores['intent_resolution'] >= threshold → passes gate 0."""
    config = ContractConfig(require_intent_resolution=True)
    contract = TaskAdherenceContract(config)
    evidence = Evidence(
        outputs={"terminal_success": True},
        scores={"intent_resolution": 4.0},
    )
    intent_handled, _, codes = contract.evaluate(evidence)
    assert intent_handled is True
    assert "intent_resolution:passed" in codes


def test_intent_resolution_fails_low_score():
    """scores['intent_resolution'] below threshold → fails gate 0."""
    config = ContractConfig(require_intent_resolution=True, intent_resolution_threshold=3.0)
    contract = TaskAdherenceContract(config)
    evidence = Evidence(
        outputs={"terminal_success": True},
        scores={"intent_resolution": 2.0},
    )
    intent_handled, _, codes = contract.evaluate(evidence)
    assert intent_handled is False
    assert any("intent_resolution:score_below_threshold" in c for c in codes)


def test_intent_resolution_passes_with_flag():
    """outputs['intent_handled'] = True → passes gate 0."""
    config = ContractConfig(require_intent_resolution=True)
    contract = TaskAdherenceContract(config)
    evidence = Evidence(outputs={"terminal_success": True, "intent_handled": True})
    intent_handled, _, codes = contract.evaluate(evidence)
    assert intent_handled is True
    assert "intent_resolution:passed" in codes


def test_intent_resolution_passes_with_query_response():
    """query + response present → passes gate 0."""
    config = ContractConfig(require_intent_resolution=True)
    contract = TaskAdherenceContract(config)
    evidence = Evidence(
        outputs={"terminal_success": True},
        query="What are the hours?",
        response="Open 9-5.",
    )
    intent_handled, _, codes = contract.evaluate(evidence)
    assert intent_handled is True
    assert "intent_resolution:passed" in codes


def test_intent_resolution_fails_no_evidence():
    """No resolution evidence → fails gate 0."""
    config = ContractConfig(require_intent_resolution=True)
    contract = TaskAdherenceContract(config)
    evidence = Evidence(outputs={"terminal_success": True})
    intent_handled, _, codes = contract.evaluate(evidence)
    assert intent_handled is False
    assert "intent_resolution:failed" in codes


def test_intent_resolution_custom_threshold():
    """Custom threshold is respected."""
    config = ContractConfig(require_intent_resolution=True, intent_resolution_threshold=4.0)
    contract = TaskAdherenceContract(config)
    # Score of 3.5 is below custom threshold of 4.0
    evidence = Evidence(
        outputs={"terminal_success": True},
        scores={"intent_resolution": 3.5},
    )
    intent_handled, _, _ = contract.evaluate(evidence)
    assert intent_handled is False


# ---- Terminal success gate ------------------------------------------------


def test_terminal_success_with_flag():
    """outputs['terminal_success'] = True → passes gate 1."""
    contract = TaskAdherenceContract()
    evidence = Evidence(outputs={"terminal_success": True})
    _, adhered, codes = contract.evaluate(evidence)
    assert adhered is True
    assert "terminal_success:passed" in codes


def test_terminal_success_with_status_completed():
    """outputs['status'] = 'completed' → passes gate 1."""
    contract = TaskAdherenceContract()
    evidence = Evidence(outputs={"status": "completed"})
    _, adhered, codes = contract.evaluate(evidence)
    assert adhered is True
    assert "terminal_success:passed" in codes


def test_terminal_success_with_status_success():
    """outputs['status'] = 'success' → passes gate 1."""
    contract = TaskAdherenceContract()
    evidence = Evidence(outputs={"status": "Success"})
    _, adhered, _ = contract.evaluate(evidence)
    assert adhered is True


def test_terminal_success_fails_with_no_signal():
    """No success signal → fails gate 1."""
    contract = TaskAdherenceContract()
    evidence = Evidence(outputs={"result": "some data"})
    _, adhered, codes = contract.evaluate(evidence)
    assert adhered is False
    assert "terminal_success:failed" in codes


def test_terminal_success_fails_with_wrong_status():
    """status='failed' → fails gate 1."""
    contract = TaskAdherenceContract()
    evidence = Evidence(outputs={"status": "failed"})
    _, adhered, codes = contract.evaluate(evidence)
    assert adhered is False
    assert "terminal_success:failed" in codes


# ---- Required outputs gate -----------------------------------------------


def test_required_outputs_passes():
    """All required keys present → passes gate 2."""
    config = ContractConfig(required_output_keys=["result", "summary"])
    contract = TaskAdherenceContract(config)
    evidence = Evidence(
        outputs={"terminal_success": True, "result": "ok", "summary": "done"}
    )
    _, adhered, codes = contract.evaluate(evidence)
    assert adhered is True
    assert "required_outputs:passed" in codes


def test_required_outputs_fails_missing_key():
    """Missing a required key → fails gate 2."""
    config = ContractConfig(required_output_keys=["result", "summary"])
    contract = TaskAdherenceContract(config)
    evidence = Evidence(outputs={"terminal_success": True, "result": "ok"})
    _, adhered, codes = contract.evaluate(evidence)
    assert adhered is False
    assert any("required_outputs:missing" in c for c in codes)


def test_required_outputs_skipped_when_empty():
    """No required keys configured → gate 2 is skipped."""
    contract = TaskAdherenceContract()
    evidence = Evidence(outputs={"terminal_success": True})
    _, _, codes = contract.evaluate(evidence)
    assert "required_outputs:skipped" in codes


# ---- Output validation gate -----------------------------------------------


def test_output_validation_passes():
    """Non-null, non-empty values → passes gate 3."""
    contract = TaskAdherenceContract()
    evidence = Evidence(outputs={"terminal_success": True, "data": "value"})
    _, adhered, codes = contract.evaluate(evidence)
    assert adhered is True
    assert "output_validation:passed" in codes


def test_output_validation_fails_null_value():
    """A null value → fails gate 3."""
    contract = TaskAdherenceContract()
    evidence = Evidence(outputs={"terminal_success": True, "bad": None})
    _, adhered, codes = contract.evaluate(evidence)
    assert adhered is False
    assert any("output_validation:invalid" in c for c in codes)


def test_output_validation_fails_empty_string():
    """An empty string value → fails gate 3."""
    contract = TaskAdherenceContract()
    evidence = Evidence(outputs={"terminal_success": True, "empty": ""})
    _, adhered, codes = contract.evaluate(evidence)
    assert adhered is False
    assert any("output_validation:invalid" in c for c in codes)


def test_output_validation_whitespace_only_fails():
    """A whitespace-only string → fails gate 3."""
    contract = TaskAdherenceContract()
    evidence = Evidence(outputs={"terminal_success": True, "ws": "   "})
    _, adhered, codes = contract.evaluate(evidence)
    assert adhered is False


# ---- Approval gate -------------------------------------------------------


def test_approval_skipped_by_default():
    """When require_approval=False, gate 4 is skipped."""
    contract = TaskAdherenceContract()
    evidence = Evidence(outputs={"terminal_success": True})
    _, _, codes = contract.evaluate(evidence)
    assert "approval:skipped" in codes


def test_approval_passes():
    """approved=True → passes gate 4."""
    config = ContractConfig(require_approval=True)
    contract = TaskAdherenceContract(config)
    evidence = Evidence(outputs={"terminal_success": True, "approved": True})
    _, adhered, codes = contract.evaluate(evidence)
    assert adhered is True
    assert "approval:passed" in codes


def test_approval_fails():
    """approved missing or falsy → fails gate 4."""
    config = ContractConfig(require_approval=True)
    contract = TaskAdherenceContract(config)
    evidence = Evidence(outputs={"terminal_success": True})
    _, adhered, codes = contract.evaluate(evidence)
    assert adhered is False
    assert "approval:failed" in codes


# ---- Combined / acceptance criteria --------------------------------------


def test_passing_payload_billable():
    """Full passing payload → adhered=True (billable_units would be 1)."""
    contract = TaskAdherenceContract()
    evidence = Evidence(outputs={"terminal_success": True, "result": "done"})
    _, adhered, codes = contract.evaluate(evidence)
    assert adhered is True
    assert all("failed" not in c for c in codes)


def test_failing_payload_not_billable():
    """Missing success signal → adhered=False (billable_units would be 0)."""
    contract = TaskAdherenceContract()
    evidence = Evidence(outputs={})
    _, adhered, codes = contract.evaluate(evidence)
    assert adhered is False
    assert "terminal_success:failed" in codes


def test_all_reason_codes_collected():
    """Even when gates fail, all five gates still produce reason codes."""
    config = ContractConfig(
        required_output_keys=["x"],
        require_approval=True,
        require_intent_resolution=True,
    )
    contract = TaskAdherenceContract(config)
    evidence = Evidence(outputs={})
    _, _, codes = contract.evaluate(evidence)
    assert len(codes) == 5


def test_intent_and_adherence_both_required():
    """intent_handled=False even when adhered=True means not billable."""
    config = ContractConfig(require_intent_resolution=True)
    contract = TaskAdherenceContract(config)
    evidence = Evidence(outputs={"terminal_success": True})
    intent_handled, adhered, _ = contract.evaluate(evidence)
    assert intent_handled is False
    assert adhered is True
