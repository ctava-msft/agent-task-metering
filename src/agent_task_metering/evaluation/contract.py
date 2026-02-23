"""Task Intent Adherence Contract — deterministic gate evaluation.

Implements five sequential gates that an agent task must pass in order to be
considered *adhered* and therefore billable:

0. **Intent resolution** (optional) — the evidence must indicate that the
   user's intent was identified and resolved.
1. **Terminal success** — the evidence must indicate the task reached a
   terminal success state.
2. **Required outputs** — a configurable set of output keys must be present.
3. **Output validation** — present outputs must be non-null / non-empty.
4. **Approval gate** (optional) — if enabled, an explicit ``approved`` flag
   must be truthy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from .models import Evidence

# Recognised values for the "status" output key that count as success.
_SUCCESS_STATUSES = frozenset({"completed", "success"})


@dataclass
class ContractConfig:
    """Configuration knobs for the adherence contract.

    Parameters
    ----------
    required_output_keys : list[str]
        Output keys that *must* be present for the required-outputs gate.
    require_approval : bool
        When *True*, the approval gate is active.
    require_intent_resolution : bool
        When *True*, the intent resolution gate is active.
    intent_resolution_threshold : float
        Minimum ``scores["intent_resolution"]`` value to pass the intent
        resolution gate (matches Azure AI Evaluation SDK default of 3).
    """

    required_output_keys: List[str] = field(default_factory=list)
    require_approval: bool = False
    require_intent_resolution: bool = False
    intent_resolution_threshold: float = 3.0


class TaskAdherenceContract:
    """Evaluates evidence against a set of deterministic adherence gates.

    Parameters
    ----------
    config : ContractConfig, optional
        Contract configuration.  Defaults to the permissive baseline
        (no required keys, no approval gate, no intent resolution gate).
    """

    def __init__(self, config: ContractConfig | None = None) -> None:
        self._config = config or ContractConfig()

    # ------------------------------------------------------------------
    # Individual gates
    # ------------------------------------------------------------------

    def _gate_intent_resolution(self, evidence: Evidence) -> Tuple[bool, str]:
        """Gate 0 (optional) — user intent must be resolved.

        Passes when **any** of the following hold:

        * ``evidence.scores["intent_resolution"]`` ≥ threshold
        * ``evidence.outputs["intent_handled"]`` is truthy
        * Both ``evidence.query`` and ``evidence.response`` are non-empty
        """
        if not self._config.require_intent_resolution:
            return True, "intent_resolution:skipped"

        # Score from Azure AI Evaluation SDK
        score = evidence.scores.get("intent_resolution")
        if score is not None:
            if score >= self._config.intent_resolution_threshold:
                return True, "intent_resolution:passed"
            return False, f"intent_resolution:score_below_threshold={score}"

        # Explicit flag
        if evidence.outputs.get("intent_handled"):
            return True, "intent_resolution:passed"

        # Query + response presence
        if evidence.query and evidence.response:
            return True, "intent_resolution:passed"

        return False, "intent_resolution:failed"

    @staticmethod
    def _gate_terminal_success(outputs: Dict[str, Any]) -> Tuple[bool, str]:
        """Gate 1 — evidence must signal terminal success."""
        if outputs.get("terminal_success"):
            return True, "terminal_success:passed"

        status = outputs.get("status", "")
        if isinstance(status, str) and status.lower() in _SUCCESS_STATUSES:
            return True, "terminal_success:passed"

        return False, "terminal_success:failed"

    def _gate_required_outputs(self, outputs: Dict[str, Any]) -> Tuple[bool, str]:
        """Gate 2 — all configured required output keys must be present."""
        if not self._config.required_output_keys:
            return True, "required_outputs:skipped"

        missing = [k for k in self._config.required_output_keys if k not in outputs]
        if missing:
            return False, f"required_outputs:missing={','.join(missing)}"
        return True, "required_outputs:passed"

    @staticmethod
    def _gate_output_validation(outputs: Dict[str, Any]) -> Tuple[bool, str]:
        """Gate 3 — present output values must be non-null and non-empty."""
        invalid = []
        for key, value in outputs.items():
            if value is None:
                invalid.append(key)
            elif isinstance(value, str) and value.strip() == "":
                invalid.append(key)
        if invalid:
            return False, f"output_validation:invalid={','.join(invalid)}"
        return True, "output_validation:passed"

    def _gate_approval(self, outputs: Dict[str, Any]) -> Tuple[bool, str]:
        """Gate 4 (optional) — explicit approval flag must be truthy."""
        if not self._config.require_approval:
            return True, "approval:skipped"

        if outputs.get("approved"):
            return True, "approval:passed"
        return False, "approval:failed"

    # ------------------------------------------------------------------
    # Public evaluation entry-point
    # ------------------------------------------------------------------

    def evaluate(self, evidence: Evidence) -> Tuple[bool, bool, List[str]]:
        """Run all gates against *evidence*.

        Returns
        -------
        tuple[bool, bool, list[str]]
            ``(intent_handled, adhered, reason_codes)`` where
            *intent_handled* reflects gate 0 and *adhered* reflects
            gates 1-4.  All gates execute regardless of earlier failures
            so that every reason code is collected for audit purposes.
        """
        intent_gate = self._gate_intent_resolution(evidence)

        outputs = evidence.outputs
        adherence_gates = [
            self._gate_terminal_success(outputs),
            self._gate_required_outputs(outputs),
            self._gate_output_validation(outputs),
            self._gate_approval(outputs),
        ]

        intent_handled = intent_gate[0]
        adhered = all(passed for passed, _ in adherence_gates)
        reason_codes = [intent_gate[1]] + [code for _, code in adherence_gates]
        return intent_handled, adhered, reason_codes
