# Audit Logging & Billing Traceability

This document explains the structured audit-logging pipeline added by the
`agent-task-metering` package and how to query "what got billed and why."

## End-to-End Trace Path

Every metered event carries a **correlation ID** that threads through the
full pipeline:

```
task → evaluation_decision → task_recorded → aggregation_complete → marketplace_submission
```

| Stage | Event name | Key fields |
|-------|-----------|------------|
| 1. Evaluation decision | `evaluation_decision` | `correlation_id`, `task_id`, `agent_id`, `subscription_ref`, `intent_handled`, `adhered`, `billable_units`, `reason_codes` |
| 2. Task recorded | `task_recorded` | `correlation_id`, `subscription_ref`, `task_id`, `hour_key` |
| 3. Aggregation | `aggregation_complete` | `correlation_id`, `subscription_ref`, `hour_window`, `quantity` |
| 4. Marketplace submit | `marketplace_submission` | `correlation_id`, `subscription_ref`, `hour_window`, `quantity`, `dry_run` |

All log entries are JSON-structured lines emitted by
`agent_task_metering.audit_logger.AuditLogger`. Each line includes a UTC
`timestamp`, `level`, `logger`, `message`, and the fields above.

### Example log line

```json
{
  "timestamp": "2025-06-01T14:30:00.123456+00:00",
  "level": "INFO",
  "logger": "agent_task_metering.audit",
  "message": "evaluation_decision",
  "event": "evaluation_decision",
  "correlation_id": "a1b2c3d4e5f6",
  "task_id": "task-42",
  "agent_id": "agent-7",
  "subscription_ref": "sub-abc",
  "intent_handled": true,
  "adhered": true,
  "billable_units": 1,
  "reason_codes": ["intent_resolution:skipped", "terminal_success:passed", "required_outputs:skipped", "output_validation:passed", "approval:skipped"]
}
```

## Querying "What Got Billed and Why"

### 1. Via the Audit API

```
GET /audit/<correlation_id>
```

Returns the full `AuditRecord` for a single evaluation, including the
original evidence, gate outcomes, and final billable decision.

### 2. Via structured logs

Filter structured JSON logs by `correlation_id` to see the complete
trace path for a single billing event:

```bash
# Show all events for a specific correlation ID
cat audit.log | jq 'select(.correlation_id == "a1b2c3d4e5f6")'
```

To find all billable tasks for a subscription in a time range:

```bash
cat audit.log | jq 'select(.event == "evaluation_decision" and .subscription_ref == "sub-abc" and .billable_units > 0)'
```

### 3. Via the AuditStore (programmatic)

```python
evaluator = TaskAdherenceEvaluator()
# ... after evaluations ...
for record in evaluator.audit_store.list_records():
    if record.billable_units > 0:
        print(f"{record.correlation_id}: task={record.task_id}, billed={record.billable_units}")
```

## Guardrails: Per-Subscription Caps

The `GuardrailConfig` class provides configurable per-subscription caps:

```python
from agent_task_metering.metering.client import GuardrailConfig, MarketplaceMeteringClient

client = MarketplaceMeteringClient(
    guardrail_config=GuardrailConfig(
        hourly_cap=100,   # max 100 tasks/subscription/hour
        daily_cap=1000,   # max 1000 tasks/subscription/day
    ),
)
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `hourly_cap` | `0` (unlimited) | Maximum `task_completed` events per subscription per hour |
| `daily_cap` | `0` (unlimited) | Maximum `task_completed` events per subscription per day |

### What happens when a cap is exceeded

1. `record_task_completed()` returns `False` (the task is **not** recorded).
2. An `AnomalyRecord` is created and stored on the client.
3. A `guardrail_cap_exceeded` structured log event is emitted with
   `review_needed=True`.

### Querying anomaly records

```python
for anomaly in client.anomalies:
    print(f"[{anomaly.cap_type}] sub={anomaly.subscription_ref} "
          f"task={anomaly.task_id} cap={anomaly.cap_value}")
```

Or filter logs:

```bash
cat audit.log | jq 'select(.event == "guardrail_cap_exceeded")'
```

## Correlation ID Propagation

Correlation IDs are propagated end-to-end:

- **Evaluation**: A unique `correlation_id` is auto-generated per
  `evaluate()` call and included in the `EvaluationResult` and
  `AuditRecord`.
- **API endpoints**: Accept an optional `correlation_id` in the request
  body; if omitted, one is generated automatically.
- **Metering client**: `record_task_completed()` and
  `aggregate_and_submit()` accept an optional `correlation_id` that
  appears in all structured log events.

This allows you to trace a single task from evaluation decision through
recording, aggregation, and Marketplace submission using one identifier.
