"""TaskAdherenceEvaluator — main entry-point for adherence evaluation.

Orchestrates the contract gates (including intent resolution), generates a
correlation ID, emits an audit record, and returns a deterministic
:class:`EvaluationResult`.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict

from ..audit_logger import get_audit_logger
from .audit import AuditStore
from .contract import ContractConfig, TaskAdherenceContract
from .models import AuditRecord, EvaluationRequest, EvaluationResult

_log = get_audit_logger()


class TaskAdherenceEvaluator:
    """Evaluate a task against the adherence contract and produce a billable outcome.

    Parameters
    ----------
    config : ContractConfig, optional
        Adherence gate configuration.
    audit_store : AuditStore, optional
        Where to persist audit records.  A fresh in-memory store is created
        when none is supplied.
    """

    def __init__(
        self,
        config: ContractConfig | None = None,
        audit_store: AuditStore | None = None,
    ) -> None:
        self._contract = TaskAdherenceContract(config)
        self._audit_store = audit_store if audit_store is not None else AuditStore()

    # ------------------------------------------------------------------
    # Core evaluation
    # ------------------------------------------------------------------

    def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        """Evaluate *request* and return an :class:`EvaluationResult`.

        The method is **deterministic**: the same inputs always produce
        the same ``intent_handled`` / ``adhered`` / ``billable_units``
        outcome.  A unique ``correlation_id`` is generated for each
        invocation and an :class:`AuditRecord` is persisted automatically.

        Billing requires **both** intent resolution and task adherence
        gates to pass: ``billable_units = 1`` only when
        ``intent_handled and adhered``.
        """
        correlation_id = uuid.uuid4().hex

        intent_handled, adhered, reason_codes = self._contract.evaluate(
            request.evidence
        )
        billable_units = 1 if intent_handled and adhered else 0

        result = EvaluationResult(
            intent_handled=intent_handled,
            adhered=adhered,
            billable_units=billable_units,
            reason_codes=reason_codes,
            correlation_id=correlation_id,
        )

        _log.log_event(
            "evaluation_decision",
            correlation_id=correlation_id,
            task_id=request.task_id,
            agent_id=request.agent_id,
            subscription_ref=request.subscription_ref,
            intent_handled=intent_handled,
            adhered=adhered,
            billable_units=billable_units,
            reason_codes=reason_codes,
        )

        # Persist audit trail
        audit = AuditRecord(
            correlation_id=correlation_id,
            task_id=request.task_id,
            agent_id=request.agent_id,
            subscription_ref=request.subscription_ref,
            evidence=asdict(request.evidence),
            intent_handled=intent_handled,
            adhered=adhered,
            billable_units=billable_units,
            reason_codes=reason_codes,
        )
        self._audit_store.record(audit)

        return result

    # ------------------------------------------------------------------
    # Introspection helpers
    # ------------------------------------------------------------------

    @property
    def contract(self) -> TaskAdherenceContract:
        """Access the underlying adherence contract."""
        return self._contract

    @property
    def audit_store(self) -> AuditStore:
        """Access the underlying audit store (read-only)."""
        return self._audit_store
