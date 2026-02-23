"""End-to-end quickstart: agent task → evaluate → record → aggregate → submit.

Demonstrates the full agent-task-metering pipeline in dry-run mode.

Usage:
    pip install -e ".[dev]"
    python examples/quickstart/run_quickstart.py
"""

from datetime import datetime, timezone

from agent_task_metering import (
    ContractConfig,
    EvaluationRequest,
    Evidence,
    MarketplaceMeteringClient,
    TaskAdherenceEvaluator,
)

# ── Configuration ─────────────────────────────────────────────────────
SUBSCRIPTION = "sub-contoso-001"
PLAN_ID = "basic"
HOUR = datetime(2025, 6, 1, 14, 0, 0, tzinfo=timezone.utc)

# ── 1. Set up evaluator and metering client ───────────────────────────
evaluator = TaskAdherenceEvaluator(config=ContractConfig())
client = MarketplaceMeteringClient(dry_run=True, plan_id=PLAN_ID)

# ── 2. Simulate agent task completions ────────────────────────────────
tasks = [
    {
        "task_id": "task-001",
        "agent_id": "agent-alpha",
        "outputs": {"status": "completed", "result": "Summary generated"},
    },
    {
        "task_id": "task-002",
        "agent_id": "agent-alpha",
        "outputs": {"status": "completed", "result": "Report created"},
    },
    {
        "task_id": "task-003",
        "agent_id": "agent-beta",
        "outputs": {"status": "completed", "result": "Data analyzed"},
    },
    # This task FAILS the adherence contract (empty output value).
    {
        "task_id": "task-004",
        "agent_id": "agent-beta",
        "outputs": {"status": "completed", "result": ""},
    },
]

print("=" * 60)
print("  agent-task-metering · End-to-End Quickstart")
print("=" * 60)

# ── 3. Evaluate each task ─────────────────────────────────────────────
print("\n── Step 1: Evaluate tasks ──\n")
for t in tasks:
    request = EvaluationRequest(
        task_id=t["task_id"],
        agent_id=t["agent_id"],
        subscription_ref=SUBSCRIPTION,
        evidence=Evidence(outputs=t["outputs"]),
    )
    result = evaluator.evaluate(request)
    status = "✅ BILLABLE" if result.billable_units else "❌ NOT BILLABLE"
    print(
        f"  {t['task_id']}: {status}  "
        f"(intent={result.intent_handled}, adhered={result.adhered}, "
        f"cid={result.correlation_id[:8]}…)"
    )
    print(f"    reason_codes: {result.reason_codes}")

    # ── 4. Record billable tasks ──────────────────────────────────────
    if result.billable_units:
        recorded = client.record_task_completed(
            subscription_ref=SUBSCRIPTION,
            task_id=t["task_id"],
            timestamp=HOUR.replace(minute=int(t["task_id"][-1]) * 10),
            correlation_id=result.correlation_id,
        )
        print(f"    recorded: {recorded}")

# ── 5. Demonstrate duplicate protection ───────────────────────────────
print("\n── Step 2: Duplicate protection ──\n")
dup = client.record_task_completed(
    subscription_ref=SUBSCRIPTION,
    task_id="task-001",  # already recorded above
    timestamp=HOUR.replace(minute=55),
)
print(f"  Re-record task-001: new={dup}  (expected False)")

# ── 6. Aggregate and submit (dry-run) ─────────────────────────────────
print("\n── Step 3: Aggregate & submit (dry-run) ──\n")
hour_key = "2025-06-01T14:00:00Z"
events = client.aggregate_and_submit(hour_key)
print(f"\n  Events emitted: {len(events)}")
for ev in events:
    print(
        f"    {ev.resourceId}: quantity={ev.quantity}, "
        f"dimension={ev.dimension}, hour={ev.effectiveStartTime}"
    )

# ── 7. Idempotent re-submission ───────────────────────────────────────
print("\n── Step 4: Idempotent re-submission ──\n")
events2 = client.aggregate_and_submit(hour_key)
print(f"  Events on retry: {len(events2)}  (expected 0)")

# ── 8. Audit trail ────────────────────────────────────────────────────
print("\n── Step 5: Audit trail ──\n")
records = evaluator.audit_store.list_records()
print(f"  Audit records stored: {len(records)}")
for rec in records:
    billed = "billed" if rec.billable_units else "not billed"
    print(f"    {rec.task_id}: {billed} (cid={rec.correlation_id[:8]}…)")

print("\n" + "=" * 60)
print("  Done. One usage event per hour per subscription for N tasks.")
print("=" * 60)
