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
from typing import Callable, Dict, List, Optional, Set, Tuple

DIMENSION = "task_completed"


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
    """

    def __init__(
        self,
        dry_run: bool = True,
        submit_callback: Optional[Callable[[Dict], None]] = None,
        plan_id: str = "",
    ) -> None:
        self._dry_run = dry_run
        self._submit_callback = submit_callback
        self._plan_id = plan_id
        # {(subscription_ref, hour_key): set_of_task_ids}
        self._completions: Dict[Tuple[str, str], Set[str]] = field(
            default_factory=dict
        ) if False else {}
        # track submitted hour windows for idempotency
        self._submitted: Set[Tuple[str, str]] = set()

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
    ) -> bool:
        """Record a single ``task_completed`` event.

        Returns *True* if the task was newly recorded, *False* if it was
        a duplicate within the same hour (idempotent).
        """
        ts = timestamp or datetime.now(timezone.utc)
        hk = self._hour_key(ts)
        key = (subscription_ref, hk)

        if key not in self._completions:
            self._completions[key] = set()

        if task_id in self._completions[key]:
            return False  # duplicate — already recorded for this hour

        self._completions[key].add(task_id)
        return True

    # ------------------------------------------------------------------
    # Aggregation & submission
    # ------------------------------------------------------------------

    def aggregate_and_submit(
        self,
        hour_window: Optional[str] = None,
    ) -> List[UsageEvent]:
        """Aggregate recorded completions and emit usage events.

        Parameters
        ----------
        hour_window : str, optional
            ISO-8601 hour string (e.g. ``"2025-06-01T14:00:00Z"``).
            If omitted, **all** recorded (and not-yet-submitted) windows
            are processed.

        Returns
        -------
        list[UsageEvent]
            The usage events that were emitted (one per subscription per
            hour window).
        """
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

            if self._dry_run:
                print(
                    f"[dry-run] Usage event: {json.dumps(event.to_dict(), indent=2)}"
                )
            elif self._submit_callback is not None:
                self._submit_callback(event.to_dict())

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
    def dry_run(self) -> bool:
        return self._dry_run
