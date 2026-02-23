"""Marketplace metering client with hourly aggregation and idempotency.

Reuses accounting, aggregation, and idempotency patterns from:
- microsoft/metered-billing-accelerator
- microsoft/commercial-marketplace-solutions (SaaS + metered-engine samples)

Key Marketplace constraints enforced:
- Only one usage event per hour per dimension per resource
- Aggregate quantity within the hour
- Dimension is exactly ``task_completed``
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from ..audit_logger import get_audit_logger

DIMENSION = "task_completed"

_log = get_audit_logger()


@dataclass
class UsageEvent:
    """Azure Marketplace usage event payload (single dimension)."""

    resourceId: str
    quantity: int
    dimension: str
    effectiveStartTime: str
    planId: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class AnomalyRecord:
    """Recorded when a guardrail cap is exceeded for a subscription."""

    subscription_ref: str
    cap_type: str
    cap_value: int
    actual_value: int
    task_id: str
    correlation_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return d


@dataclass
class GuardrailConfig:
    """Configurable caps for per-subscription metering guardrails.

    Parameters
    ----------
    hourly_cap : int
        Maximum ``task_completed`` events per subscription per hour.
        ``0`` means unlimited.
    daily_cap : int
        Maximum ``task_completed`` events per subscription per day.
        ``0`` means unlimited.
    """

    hourly_cap: int = 0
    daily_cap: int = 0


class MarketplaceMeteringClient:
    """Records task completions and emits aggregated Marketplace usage events.

    Parameters
    ----------
    dry_run : bool
        When *True* (default), events are printed instead of submitted.
    submit_callback : callable, optional
        ``f(event_dict) -> None`` called for each aggregated event when
        *dry_run* is False.  Plug in real Marketplace API calls here.
    plan_id : str
        Marketplace plan ID attached to every usage event.
    guardrail_config : GuardrailConfig, optional
        Per-subscription hourly/daily caps.
    """

    def __init__(
        self,
        dry_run: bool = True,
        submit_callback: Optional[Callable[[Dict], None]] = None,
        plan_id: str = "",
        guardrail_config: Optional[GuardrailConfig] = None,
    ) -> None:
        self._dry_run = dry_run
        self._submit_callback = submit_callback
        self._plan_id = plan_id
        self._guardrail = guardrail_config or GuardrailConfig()
        # {(subscription_ref, hour_key): set_of_task_ids}
        self._completions: Dict[Tuple[str, str], Set[str]] = {}
        # track submitted hour windows for idempotency
        self._submitted: Set[Tuple[str, str]] = set()
        # anomaly records created when caps are breached
        self._anomalies: List[AnomalyRecord] = []

    # ------------------------------------------------------------------
    # Cap helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _day_key(ts: datetime) -> str:
        """Return the ISO-8601 day bucket for *ts* (UTC, truncated to day)."""
        utc = ts.astimezone(timezone.utc) if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        return utc.strftime("%Y-%m-%d")

    def _hourly_count(self, subscription_ref: str, hour_key: str) -> int:
        return len(self._completions.get((subscription_ref, hour_key), set()))

    def _daily_count(self, subscription_ref: str, day_key: str) -> int:
        total = 0
        for (sub, hk), tasks in self._completions.items():
            if sub == subscription_ref and hk.startswith(day_key):
                total += len(tasks)
        return total

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    @staticmethod
    def _hour_key(ts: datetime) -> str:
        """Return the ISO-8601 hour bucket for *ts* (UTC, truncated to hour)."""
        utc = ts.astimezone(timezone.utc) if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        return utc.strftime("%Y-%m-%dT%H:00:00Z")

    def record_task_completed(
        self,
        subscription_ref: str,
        task_id: str,
        timestamp: Optional[datetime] = None,
        correlation_id: Optional[str] = None,
    ) -> bool:
        """Record a single ``task_completed`` event.

        Returns *True* if the task was newly recorded, *False* if it was
        a duplicate within the same hour (idempotent) **or** if a
        guardrail cap was exceeded.
        """
        cid = correlation_id or ""
        ts = timestamp or datetime.now(timezone.utc)
        hk = self._hour_key(ts)
        dk = self._day_key(ts)
        key = (subscription_ref, hk)

        if key not in self._completions:
            self._completions[key] = set()

        if task_id in self._completions[key]:
            _log.log_event(
                "task_recording_duplicate",
                correlation_id=cid,
                subscription_ref=subscription_ref,
                task_id=task_id,
                hour_key=hk,
            )
            return False  # duplicate — already recorded for this hour

        # --- Guardrail: hourly cap ---
        if self._guardrail.hourly_cap > 0:
            hourly_count = self._hourly_count(subscription_ref, hk)
            if hourly_count >= self._guardrail.hourly_cap:
                anomaly = AnomalyRecord(
                    subscription_ref=subscription_ref,
                    cap_type="hourly",
                    cap_value=self._guardrail.hourly_cap,
                    actual_value=hourly_count,
                    task_id=task_id,
                    correlation_id=cid,
                    timestamp=ts,
                )
                self._anomalies.append(anomaly)
                _log.log_event(
                    "guardrail_cap_exceeded",
                    correlation_id=cid,
                    subscription_ref=subscription_ref,
                    cap_type="hourly",
                    cap_value=self._guardrail.hourly_cap,
                    actual=hourly_count,
                    task_id=task_id,
                    review_needed=True,
                )
                return False

        # --- Guardrail: daily cap ---
        if self._guardrail.daily_cap > 0:
            daily_count = self._daily_count(subscription_ref, dk)
            if daily_count >= self._guardrail.daily_cap:
                anomaly = AnomalyRecord(
                    subscription_ref=subscription_ref,
                    cap_type="daily",
                    cap_value=self._guardrail.daily_cap,
                    actual_value=daily_count,
                    task_id=task_id,
                    correlation_id=cid,
                    timestamp=ts,
                )
                self._anomalies.append(anomaly)
                _log.log_event(
                    "guardrail_cap_exceeded",
                    correlation_id=cid,
                    subscription_ref=subscription_ref,
                    cap_type="daily",
                    cap_value=self._guardrail.daily_cap,
                    actual=daily_count,
                    task_id=task_id,
                    review_needed=True,
                )
                return False

        self._completions[key].add(task_id)

        _log.log_event(
            "task_recorded",
            correlation_id=cid,
            subscription_ref=subscription_ref,
            task_id=task_id,
            hour_key=hk,
        )
        return True

    # ------------------------------------------------------------------
    # Aggregation & submission
    # ------------------------------------------------------------------

    def aggregate_and_submit(
        self,
        hour_window: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> List[UsageEvent]:
        """Aggregate recorded completions and emit usage events.

        Parameters
        ----------
        hour_window : str, optional
            ISO-8601 hour string (e.g. ``"2025-06-01T14:00:00Z"``).
            If omitted, **all** recorded (and not-yet-submitted) windows
            are processed.
        correlation_id : str, optional
            Trace identifier to include in structured logs.

        Returns
        -------
        list[UsageEvent]
            The usage events that were emitted (one per subscription per
            hour window).
        """
        cid = correlation_id or ""
        events: List[UsageEvent] = []

        keys = (
            [k for k in self._completions if k[1] == hour_window]
            if hour_window
            else list(self._completions)
        )

        for key in keys:
            if key in self._submitted:
                continue  # already submitted — idempotent guard

            subscription_ref, hk = key
            quantity = len(self._completions[key])
            if quantity == 0:
                continue

            event = UsageEvent(
                resourceId=subscription_ref,
                quantity=quantity,
                dimension=DIMENSION,
                effectiveStartTime=hk,
                planId=self._plan_id,
            )

            _log.log_event(
                "aggregation_complete",
                correlation_id=cid,
                subscription_ref=subscription_ref,
                hour_window=hk,
                quantity=quantity,
            )

            if self._dry_run:
                print(
                    f"[dry-run] Usage event: {json.dumps(event.to_dict(), indent=2)}"
                )
            elif self._submit_callback is not None:
                self._submit_callback(event.to_dict())

            _log.log_event(
                "marketplace_submission",
                correlation_id=cid,
                subscription_ref=subscription_ref,
                hour_window=hk,
                quantity=quantity,
                dry_run=self._dry_run,
            )

            self._submitted.add(key)
            events.append(event)

        return events

    # ------------------------------------------------------------------
    # Introspection helpers
    # ------------------------------------------------------------------

    def pending_quantity(
        self, subscription_ref: str, hour_window: str
    ) -> int:
        """Return the number of unique tasks recorded for a window."""
        return len(self._completions.get((subscription_ref, hour_window), set()))

    @property
    def anomalies(self) -> List[AnomalyRecord]:
        """Return all anomaly records created by guardrail cap breaches."""
        return list(self._anomalies)

    @property
    def dry_run(self) -> bool:
        return self._dry_run
