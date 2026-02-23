"""agent-task-metering: track and meter AI agent task usage."""

from .audit_logger import AuditLogger, get_audit_logger
from .evaluation import (
    AuditRecord,
    AuditStore,
    ContractConfig,
    EvaluationRequest,
    EvaluationResult,
    Evidence,
    TaskAdherenceContract,
    TaskAdherenceEvaluator,
)
from .meter import TaskMeter
from .metering import AnomalyRecord, GuardrailConfig, MarketplaceMeteringClient, UsageEvent
from .models import TaskRecord

__version__ = "0.1.0"
__all__ = [
    "AnomalyRecord",
    "AuditLogger",
    "AuditRecord",
    "AuditStore",
    "ContractConfig",
    "Evidence",
    "EvaluationRequest",
    "EvaluationResult",
    "GuardrailConfig",
    "MarketplaceMeteringClient",
    "TaskAdherenceContract",
    "TaskAdherenceEvaluator",
    "TaskMeter",
    "TaskRecord",
    "UsageEvent",
    "get_audit_logger",
]
