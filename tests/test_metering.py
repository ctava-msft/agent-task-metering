"""Unit tests for the metering module (MarketplaceMeteringClient)."""

from datetime import datetime, timezone

from agent_task_metering.metering.client import (
    DIMENSION,
    MarketplaceMeteringClient,
    UsageEvent,
)

# ---- Hourly aggregation --------------------------------------------------


def test_aggregation_single_subscription():
    """N completions in the same hour → 1 event with quantity=N."""
    client = MarketplaceMeteringClient(dry_run=True)
    ts = datetime(2025, 6, 1, 14, 10, 0, tzinfo=timezone.utc)
    for i in range(12):
        client.record_task_completed("sub-1", f"task-{i}", ts)

    events = client.aggregate_and_submit("2025-06-01T14:00:00Z")
    assert len(events) == 1
    assert events[0].quantity == 12
    assert events[0].resourceId == "sub-1"
    assert events[0].dimension == DIMENSION
    assert events[0].effectiveStartTime == "2025-06-01T14:00:00Z"


def test_aggregation_multiple_subscriptions():
    """Different subscriptions in the same hour → separate events."""
    client = MarketplaceMeteringClient(dry_run=True)
    ts = datetime(2025, 6, 1, 14, 0, 0, tzinfo=timezone.utc)
    client.record_task_completed("sub-A", "t1", ts)
    client.record_task_completed("sub-A", "t2", ts)
    client.record_task_completed("sub-B", "t3", ts)

    events = client.aggregate_and_submit("2025-06-01T14:00:00Z")
    assert len(events) == 2
    by_sub = {e.resourceId: e for e in events}
    assert by_sub["sub-A"].quantity == 2
    assert by_sub["sub-B"].quantity == 1


def test_aggregation_multiple_hours():
    """Tasks in different hours produce separate events."""
    client = MarketplaceMeteringClient(dry_run=True)
    client.record_task_completed(
        "sub-1", "t1", datetime(2025, 6, 1, 14, 5, 0, tzinfo=timezone.utc)
    )
    client.record_task_completed(
        "sub-1", "t2", datetime(2025, 6, 1, 15, 5, 0, tzinfo=timezone.utc)
    )

    events = client.aggregate_and_submit()
    assert len(events) == 2
    quantities = sorted(e.effectiveStartTime for e in events)
    assert quantities == ["2025-06-01T14:00:00Z", "2025-06-01T15:00:00Z"]


# ---- Duplicate / idempotency --------------------------------------------


def test_duplicate_task_same_hour_ignored():
    """Recording the same task_id twice in the same hour is idempotent."""
    client = MarketplaceMeteringClient(dry_run=True)
    ts = datetime(2025, 6, 1, 14, 0, 0, tzinfo=timezone.utc)

    assert client.record_task_completed("sub-1", "t1", ts) is True
    assert client.record_task_completed("sub-1", "t1", ts) is False  # dup

    events = client.aggregate_and_submit("2025-06-01T14:00:00Z")
    assert events[0].quantity == 1


def test_same_task_different_hours_both_counted():
    """Same task_id in different hours is treated as two distinct events."""
    client = MarketplaceMeteringClient(dry_run=True)
    assert client.record_task_completed(
        "sub-1", "t1", datetime(2025, 6, 1, 14, 0, 0, tzinfo=timezone.utc)
    ) is True
    assert client.record_task_completed(
        "sub-1", "t1", datetime(2025, 6, 1, 15, 0, 0, tzinfo=timezone.utc)
    ) is True

    events = client.aggregate_and_submit()
    assert len(events) == 2
    assert all(e.quantity == 1 for e in events)


def test_resubmit_same_window_idempotent():
    """Calling aggregate_and_submit for the same window twice is a no-op."""
    client = MarketplaceMeteringClient(dry_run=True)
    ts = datetime(2025, 6, 1, 14, 0, 0, tzinfo=timezone.utc)
    client.record_task_completed("sub-1", "t1", ts)

    first = client.aggregate_and_submit("2025-06-01T14:00:00Z")
    second = client.aggregate_and_submit("2025-06-01T14:00:00Z")
    assert len(first) == 1
    assert len(second) == 0  # already submitted


# ---- Dimension -----------------------------------------------------------


def test_dimension_is_task_completed():
    """Every event uses the canonical 'task_completed' dimension."""
    client = MarketplaceMeteringClient(dry_run=True)
    ts = datetime(2025, 6, 1, 14, 0, 0, tzinfo=timezone.utc)
    client.record_task_completed("sub-1", "t1", ts)

    events = client.aggregate_and_submit()
    assert all(e.dimension == "task_completed" for e in events)


# ---- Dry-run & callback --------------------------------------------------


def test_dry_run_does_not_call_callback(capsys):
    """In dry-run mode the callback is NOT invoked, but output is printed."""
    called = []
    client = MarketplaceMeteringClient(
        dry_run=True, submit_callback=lambda e: called.append(e)
    )
    ts = datetime(2025, 6, 1, 14, 0, 0, tzinfo=timezone.utc)
    client.record_task_completed("sub-1", "t1", ts)
    client.aggregate_and_submit()

    assert len(called) == 0
    captured = capsys.readouterr()
    assert "[dry-run]" in captured.out
    assert "task_completed" in captured.out


def test_callback_invoked_when_not_dry_run():
    """With dry_run=False, the submit_callback receives the event dict."""
    submitted = []
    client = MarketplaceMeteringClient(
        dry_run=False, submit_callback=lambda e: submitted.append(e)
    )
    ts = datetime(2025, 6, 1, 14, 0, 0, tzinfo=timezone.utc)
    client.record_task_completed("sub-1", "t1", ts)
    client.aggregate_and_submit()

    assert len(submitted) == 1
    assert submitted[0]["dimension"] == "task_completed"
    assert submitted[0]["quantity"] == 1


# ---- Helpers & edge cases ------------------------------------------------


def test_pending_quantity():
    client = MarketplaceMeteringClient(dry_run=True)
    ts = datetime(2025, 6, 1, 14, 0, 0, tzinfo=timezone.utc)
    client.record_task_completed("sub-1", "t1", ts)
    client.record_task_completed("sub-1", "t2", ts)

    assert client.pending_quantity("sub-1", "2025-06-01T14:00:00Z") == 2
    assert client.pending_quantity("sub-1", "2025-06-01T15:00:00Z") == 0


def test_usage_event_to_dict():
    event = UsageEvent(
        resourceId="sub-1",
        quantity=5,
        dimension="task_completed",
        effectiveStartTime="2025-06-01T14:00:00Z",
        planId="plan-basic",
    )
    d = event.to_dict()
    assert d["resourceId"] == "sub-1"
    assert d["quantity"] == 5
    assert d["dimension"] == "task_completed"
    assert d["planId"] == "plan-basic"


def test_record_default_timestamp():
    """record_task_completed with no explicit timestamp still works."""
    client = MarketplaceMeteringClient(dry_run=True)
    assert client.record_task_completed("sub-1", "t1") is True
    events = client.aggregate_and_submit()
    assert len(events) == 1
    assert events[0].quantity == 1


def test_plan_id_propagated():
    client = MarketplaceMeteringClient(dry_run=True, plan_id="enterprise")
    ts = datetime(2025, 6, 1, 14, 0, 0, tzinfo=timezone.utc)
    client.record_task_completed("sub-1", "t1", ts)
    events = client.aggregate_and_submit()
    assert events[0].planId == "enterprise"
