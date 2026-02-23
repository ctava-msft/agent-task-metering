"""TaskMeter: records and aggregates agent task metrics."""

from datetime import datetime
from typing import Dict, List, Optional

from .models import TaskRecord


class TaskMeter:
    """Collects and aggregates metering data for agent tasks."""

    def __init__(self) -> None:
        self._records: List[TaskRecord] = []

    def record(
        self,
        task_id: str,
        agent_id: str,
        task_type: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        metadata: Optional[Dict] = None,
    ) -> TaskRecord:
        """Record a completed (or in-progress) agent task."""
        record = TaskRecord(
            task_id=task_id,
            agent_id=agent_id,
            task_type=task_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            metadata=metadata or {},
        )
        if start_time is not None:
            record.start_time = start_time
        if end_time is not None:
            record.end_time = end_time
        self._records.append(record)
        return record

    def total_tokens(self) -> int:
        """Return the sum of all tokens across all recorded tasks."""
        return sum(r.total_tokens for r in self._records)

    def records_for_agent(self, agent_id: str) -> List[TaskRecord]:
        """Return all records for a given agent."""
        return [r for r in self._records if r.agent_id == agent_id]

    def summary(self) -> Dict:
        """Return a high-level summary of all metered tasks."""
        return {
            "total_tasks": len(self._records),
            "total_tokens": self.total_tokens(),
            "agents": list({r.agent_id for r in self._records}),
        }
