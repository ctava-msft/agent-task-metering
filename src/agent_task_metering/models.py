"""Data models for agent task metering."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Optional


@dataclass
class TaskRecord:
    """Represents a single metered agent task."""

    task_id: str
    agent_id: str
    task_type: str
    start_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    end_time: Optional[datetime] = None
    input_tokens: int = 0
    output_tokens: int = 0
    metadata: dict = field(default_factory=dict)

    @property
    def duration_seconds(self) -> Optional[float]:
        """Return task duration in seconds, or None if not yet completed."""
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time).total_seconds()

    @property
    def total_tokens(self) -> int:
        """Return total token count (input + output)."""
        return self.input_tokens + self.output_tokens
