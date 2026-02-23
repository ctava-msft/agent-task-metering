"""agent-task-metering: track and meter AI agent task usage."""

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
from .metering import MarketplaceMeteringClient, UsageEvent
from .models import TaskRecord

__version__ = "0.1.0"
__all__ = [
    "AuditRecord",
    "AuditStore",
    "ContractConfig",
    "Evidence",
    "EvaluationRequest",
    "EvaluationResult",
    "MarketplaceMeteringClient",
    "TaskAdherenceContract",
    "TaskAdherenceEvaluator",
    "TaskMeter",
    "TaskRecord",
    "UsageEvent",
]
