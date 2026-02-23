"""Unit tests for the TaskAdherenceContract."""

from agent_task_metering.evaluation.contract import ContractConfig, TaskAdherenceContract
from agent_task_metering.evaluation.models import Evidence

# ---- Terminal success gate ------------------------------------------------


def test_terminal_success_with_flag():
    """outputs['terminal_success'] = True → passes gate 1."""
    contract = TaskAdherenceContract()
    evidence = Evidence(outputs={"terminal_success": True})
    adhered, codes = contract.evaluate(evidence)
    assert adhered is True
    assert "terminal_success:passed" in codes


def test_terminal_success_with_status_completed():
    """outputs['status'] = 'completed' → passes gate 1."""
    contract = TaskAdherenceContract()
    evidence = Evidence(outputs={"status": "completed"})
    adhered, codes = contract.evaluate(evidence)
    assert adhered is True
    assert "terminal_success:passed" in codes


def test_terminal_success_with_status_success():
    """outputs['status'] = 'success' → passes gate 1."""
    contract = TaskAdherenceContract()
    evidence = Evidence(outputs={"status": "Success"})
    adhered, _ = contract.evaluate(evidence)
    assert adhered is True


def test_terminal_success_fails_with_no_signal():
    """No success signal → fails gate 1."""
    contract = TaskAdherenceContract()
    evidence = Evidence(outputs={"result": "some data"})
    adhered, codes = contract.evaluate(evidence)
    assert adhered is False
    assert "terminal_success:failed" in codes


def test_terminal_success_fails_with_wrong_status():
    """status='failed' → fails gate 1."""
    contract = TaskAdherenceContract()
    evidence = Evidence(outputs={"status": "failed"})
    adhered, codes = contract.evaluate(evidence)
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
    adhered, codes = contract.evaluate(evidence)
    assert adhered is True
    assert "required_outputs:passed" in codes


def test_required_outputs_fails_missing_key():
    """Missing a required key → fails gate 2."""
    config = ContractConfig(required_output_keys=["result", "summary"])
    contract = TaskAdherenceContract(config)
    evidence = Evidence(outputs={"terminal_success": True, "result": "ok"})
    adhered, codes = contract.evaluate(evidence)
    assert adhered is False
    assert any("required_outputs:missing" in c for c in codes)


def test_required_outputs_skipped_when_empty():
    """No required keys configured → gate 2 is skipped."""
    contract = TaskAdherenceContract()
    evidence = Evidence(outputs={"terminal_success": True})
    _, codes = contract.evaluate(evidence)
    assert "required_outputs:skipped" in codes


# ---- Output validation gate -----------------------------------------------


def test_output_validation_passes():
    """Non-null, non-empty values → passes gate 3."""
    contract = TaskAdherenceContract()
    evidence = Evidence(outputs={"terminal_success": True, "data": "value"})
    adhered, codes = contract.evaluate(evidence)
    assert adhered is True
    assert "output_validation:passed" in codes


def test_output_validation_fails_null_value():
    """A null value → fails gate 3."""
    contract = TaskAdherenceContract()
    evidence = Evidence(outputs={"terminal_success": True, "bad": None})
    adhered, codes = contract.evaluate(evidence)
    assert adhered is False
    assert any("output_validation:invalid" in c for c in codes)


def test_output_validation_fails_empty_string():
    """An empty string value → fails gate 3."""
    contract = TaskAdherenceContract()
    evidence = Evidence(outputs={"terminal_success": True, "empty": ""})
    adhered, codes = contract.evaluate(evidence)
    assert adhered is False
    assert any("output_validation:invalid" in c for c in codes)


def test_output_validation_whitespace_only_fails():
    """A whitespace-only string → fails gate 3."""
    contract = TaskAdherenceContract()
    evidence = Evidence(outputs={"terminal_success": True, "ws": "   "})
    adhered, codes = contract.evaluate(evidence)
    assert adhered is False


# ---- Approval gate -------------------------------------------------------


def test_approval_skipped_by_default():
    """When require_approval=False, gate 4 is skipped."""
    contract = TaskAdherenceContract()
    evidence = Evidence(outputs={"terminal_success": True})
    _, codes = contract.evaluate(evidence)
    assert "approval:skipped" in codes


def test_approval_passes():
    """approved=True → passes gate 4."""
    config = ContractConfig(require_approval=True)
    contract = TaskAdherenceContract(config)
    evidence = Evidence(outputs={"terminal_success": True, "approved": True})
    adhered, codes = contract.evaluate(evidence)
    assert adhered is True
    assert "approval:passed" in codes


def test_approval_fails():
    """approved missing or falsy → fails gate 4."""
    config = ContractConfig(require_approval=True)
    contract = TaskAdherenceContract(config)
    evidence = Evidence(outputs={"terminal_success": True})
    adhered, codes = contract.evaluate(evidence)
    assert adhered is False
    assert "approval:failed" in codes


# ---- Combined / acceptance criteria --------------------------------------


def test_passing_payload_billable():
    """Full passing payload → adhered=True (billable_units would be 1)."""
    contract = TaskAdherenceContract()
    evidence = Evidence(outputs={"terminal_success": True, "result": "done"})
    adhered, codes = contract.evaluate(evidence)
    assert adhered is True
    assert all("failed" not in c for c in codes)


def test_failing_payload_not_billable():
    """Missing success signal → adhered=False (billable_units would be 0)."""
    contract = TaskAdherenceContract()
    evidence = Evidence(outputs={})
    adhered, codes = contract.evaluate(evidence)
    assert adhered is False
    assert "terminal_success:failed" in codes


def test_all_reason_codes_collected():
    """Even when gate 1 fails, all four gates still produce reason codes."""
    config = ContractConfig(required_output_keys=["x"], require_approval=True)
    contract = TaskAdherenceContract(config)
    evidence = Evidence(outputs={})
    _, codes = contract.evaluate(evidence)
    assert len(codes) == 4
