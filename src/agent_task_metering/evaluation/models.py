"""Data models for task adherence evaluation."""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class Evidence:
    """Evidence payload for task adherence evaluation.

    Parameters
    ----------
    outputs : dict
        Task outputs to evaluate (e.g. ``{"status": "completed", "result": ...}``).
    traces : list[dict]
        Execution traces for auditability.
    scores : dict[str, float]
        Optional numeric scores (e.g. from AI evaluation SDK).
    query : str, optional
        Original user query / intent (used by intent resolution gate).
    response : str, optional
        Agent response to the query (used by intent resolution gate).
    """

    outputs: Dict[str, Any] = field(default_factory=dict)
    traces: List[Dict[str, Any]] = field(default_factory=list)
    scores: Dict[str, float] = field(default_factory=dict)
    query: Optional[str] = None
    response: Optional[str] = None


@dataclass
class EvaluationRequest:
    """Input to the task adherence evaluation endpoint.

    Parameters
    ----------
    task_id : str
        Unique identifier of the task being evaluated.
    agent_id : str
        Identifier of the agent that executed the task.
    subscription_ref : str
        Marketplace subscription / resource reference.
    evidence : Evidence
        Outputs, traces, and optional scores produced by the agent.
    """

    task_id: str
    agent_id: str
    subscription_ref: str
    evidence: Evidence = field(default_factory=Evidence)


@dataclass
class EvaluationResult:
    """Output of the task adherence evaluation.

    Parameters
    ----------
    intent_handled : bool
        Whether the user intent was resolved by the agent.
    adhered : bool
        Whether the task met all adherence contract gates.
    billable_units : int
        ``1`` when both *intent_handled* and *adhered*, ``0`` otherwise.
    reason_codes : list[str]
        Human-readable codes describing each gate outcome.
    correlation_id : str
        Unique identifier for this evaluation (for audit trail).
    """

    intent_handled: bool
    adhered: bool
    billable_units: int
    reason_codes: List[str]
    correlation_id: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AuditRecord:
    """Immutable audit entry persisted for every evaluation decision.

    Combines the full request context with the evaluation result so that
    any billing decision can be reconstructed later.
    """

    correlation_id: str
    task_id: str
    agent_id: str
    subscription_ref: str
    evidence: Dict[str, Any]
    intent_handled: bool
    adhered: bool
    billable_units: int
    reason_codes: List[str]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return d
