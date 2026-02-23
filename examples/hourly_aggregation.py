"""Example: 12 task completions in the same hour → one usage event (quantity=12).

Demonstrates the hourly aggregation, duplicate protection, and dry-run
output of the MarketplaceMeteringClient.
"""

from datetime import datetime, timezone

from agent_task_metering.metering import MarketplaceMeteringClient

# Create a metering client in dry-run mode (default).
client = MarketplaceMeteringClient(dry_run=True, plan_id="basic")

# Simulate 12 task completions within the same hour for one subscription.
hour_ts = datetime(2025, 6, 1, 14, 0, 0, tzinfo=timezone.utc)
for i in range(1, 13):
    recorded = client.record_task_completed(
        subscription_ref="sub-contoso-001",
        task_id=f"task-{i:03d}",
        timestamp=hour_ts.replace(minute=i * 4),  # spread across the hour
    )
    print(f"  Recorded task-{i:03d}: new={recorded}")

# Also record a deliberate duplicate — it should be silently ignored.
dup = client.record_task_completed(
    subscription_ref="sub-contoso-001",
    task_id="task-001",  # same task_id as above
    timestamp=hour_ts.replace(minute=50),
)
print(f"\n  Duplicate task-001 recorded again: new={dup}  (expected False)")

# Show pending quantity before submission.
qty = client.pending_quantity("sub-contoso-001", "2025-06-01T14:00:00Z")
print(f"\nPending quantity for sub-contoso-001 @ 14:00 UTC: {qty}")

# Aggregate and submit (dry-run prints the payload).
print("\n--- Aggregation & submission ---")
events = client.aggregate_and_submit("2025-06-01T14:00:00Z")
print(f"\nEvents emitted: {len(events)}")
for ev in events:
    print(f"  {ev.resourceId}: quantity={ev.quantity}, dimension={ev.dimension}")

# Re-submitting the same window is a no-op (idempotent).
print("\n--- Re-submission (should be empty) ---")
events2 = client.aggregate_and_submit("2025-06-01T14:00:00Z")
print(f"Events emitted on retry: {len(events2)}")
