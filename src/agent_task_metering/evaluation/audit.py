"""In-memory audit store for task adherence evaluation decisions.

Every evaluation produces an :class:`AuditRecord` that is persisted here
so that billing decisions can be reconstructed for compliance purposes.
The default implementation keeps records in memory; subclass to add a
durable backend (database, blob storage, etc.).
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .models import AuditRecord


class AuditStore:
    """Thread-safe, in-memory audit log.

    Stores :class:`AuditRecord` instances keyed by ``correlation_id`` for
    fast look-up.  Iteration order matches insertion order.
    """

    def __init__(self) -> None:
        self._records: Dict[str, AuditRecord] = {}

    def record(self, audit: AuditRecord) -> None:
        """Persist an audit record.  Overwrites if correlation_id exists."""
        self._records[audit.correlation_id] = audit

    def get(self, correlation_id: str) -> Optional[AuditRecord]:
        """Retrieve a single record by its correlation ID."""
        return self._records.get(correlation_id)

    def list_records(self) -> List[AuditRecord]:
        """Return all stored records in insertion order."""
        return list(self._records.values())

    def __len__(self) -> int:
        return len(self._records)
