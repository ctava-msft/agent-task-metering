"""TaskAdherenceEvaluator — main entry-point for adherence evaluation.

Orchestrates the contract gates, generates a correlation ID, emits an
audit record, and returns a deterministic :class:`EvaluationResult`.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict

from .audit import AuditStore
from .contract import ContractConfig, TaskAdherenceContract
from .models import AuditRecord, EvaluationRequest, EvaluationResult


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
        the same ``adhered`` / ``billable_units`` outcome.  A unique
        ``correlation_id`` is generated for each invocation and an
        :class:`AuditRecord` is persisted automatically.
        """
        correlation_id = uuid.uuid4().hex

        adhered, reason_codes = self._contract.evaluate(request.evidence)
        billable_units = 1 if adhered else 0

        result = EvaluationResult(
            adhered=adhered,
            billable_units=billable_units,
            reason_codes=reason_codes,
            correlation_id=correlation_id,
        )

        # Persist audit trail
        audit = AuditRecord(
            correlation_id=correlation_id,
            task_id=request.task_id,
            agent_id=request.agent_id,
            subscription_ref=request.subscription_ref,
            evidence=asdict(request.evidence),
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
    def audit_store(self) -> AuditStore:
        """Access the underlying audit store (read-only)."""
        return self._audit_store
