"""Structured audit logger for metered billing events.

Provides a thin wrapper around Python's :mod:`logging` module that emits
JSON-structured log records.  Every log entry carries a ``correlation_id``
so that a single trace path can be reconstructed:

    task → decision → record → aggregation → submit

Usage::

    from agent_task_metering.audit_logger import get_audit_logger

    logger = get_audit_logger()
    logger.log_event("evaluation_decision", correlation_id="abc", ...)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

_LOGGER_NAME = "agent_task_metering.audit"


class _JsonFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra = getattr(record, "_structured", None)
        if extra:
            payload.update(extra)
        return json.dumps(payload, default=str)


def get_audit_logger(name: str = _LOGGER_NAME) -> "AuditLogger":
    """Return a reusable :class:`AuditLogger` instance.

    The underlying :class:`logging.Logger` is created once; subsequent
    calls with the same *name* return a wrapper around the same logger.
    """
    return AuditLogger(name)


class AuditLogger:
    """Structured logger for billing-trust audit events.

    Parameters
    ----------
    name : str
        Logger name (passed to :func:`logging.getLogger`).
    """

    def __init__(self, name: str = _LOGGER_NAME) -> None:
        self._logger = logging.getLogger(name)
        # Attach JSON handler only once per logger name.
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(_JsonFormatter())
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.DEBUG)

    def log_event(
        self,
        event: str,
        *,
        correlation_id: Optional[str] = None,
        level: int = logging.INFO,
        **fields: Any,
    ) -> Dict[str, Any]:
        """Emit a structured audit log entry and return the payload dict.

        Parameters
        ----------
        event : str
            Short event name (e.g. ``"evaluation_decision"``).
        correlation_id : str, optional
            Trace identifier propagated across the pipeline.
        level : int
            Python logging level (default ``INFO``).
        **fields
            Arbitrary key-value pairs included in the JSON payload.
        """
        structured: Dict[str, Any] = {"event": event}
        if correlation_id is not None:
            structured["correlation_id"] = correlation_id
        structured.update(fields)

        record = self._logger.makeRecord(
            self._logger.name,
            level,
            "(audit)",
            0,
            event,
            (),
            None,
        )
        record._structured = structured  # type: ignore[attr-defined]
        self._logger.handle(record)
        return structured
