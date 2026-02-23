# Billing Dimensions

This document defines the Marketplace billing dimension used by
`agent-task-metering`, what counts as billable, and how usage is aggregated.

## Dimension: `task_completed`

| Property | Value |
|---|---|
| **Dimension ID** | `task_completed` |
| **Unit** | Count of successfully completed agent tasks |
| **Granularity** | Hourly (one usage event per subscription per hour) |
| **Who is billed** | The Marketplace subscription that owns the agent |

### What Is Billable

A task increments the `task_completed` counter **only** when it passes the
full adherence contract:

1. **Intent handled** — the agent resolved the user's intent (Gate 0).
2. **Adhered** — the task passed all adherence gates (Gates 1-4: terminal
   success, required outputs, output validation, optional approval).

```
billable_units = 1  if intent_handled AND adhered
billable_units = 0  otherwise
```

This means:

- ❌ A task that **failed** (status ≠ completed/success) → not billed.
- ❌ A task that **timed out** before producing outputs → not billed.
- ❌ A task whose outputs are **empty or null** → not billed.
- ❌ A **duplicate** task in the same hour → recorded once (idempotent).
- ✅ A task that **completed successfully** with valid outputs → billed.

> **Bill outcomes, not attempts.** Only tasks that provably delivered value to
> the end user are counted. This makes billing dispute-resistant — every
> billed event has an auditable `AuditRecord` with the evidence and gate
> results that justified the charge.

### Why "Bill Outcomes, Not Attempts"

Metered billing charges appear on the customer's Azure invoice. If a charge
cannot be justified with evidence, the publisher risks a billing dispute.
By gating every charge through deterministic adherence checks and persisting
the evaluation evidence, the publisher can reconstruct exactly why a task
was billed (or not) at any point in the future.

## Hourly Aggregation Rule

The Azure Marketplace Metered Billing API requires **exactly one usage event
per resource (subscription) per dimension per hour**. The
`MarketplaceMeteringClient` enforces this:

```
Hour window  : 2025-06-01T14:00:00Z
Subscription : sub-contoso-001
Tasks billed : task-001, task-002, ..., task-012   (12 tasks in the hour)
─────────────────────────────────────────────────────────────────────────
Usage event  : { resourceId: "sub-contoso-001",
                 dimension:  "task_completed",
                 quantity:   12,
                 effectiveStartTime: "2025-06-01T14:00:00Z" }
```

### Rules

| Rule | Behaviour |
|---|---|
| **One event per hour per subscription** | All tasks within the same UTC hour are aggregated into a single usage event whose `quantity` equals the count of unique billable tasks. |
| **Duplicate protection** | If `record_task_completed()` is called twice with the same `(subscription_ref, task_id)` within the same hour, the second call is a no-op. |
| **Idempotent submission** | Calling `aggregate_and_submit()` for an already-submitted hour window returns an empty list (safe to retry). |
| **Guardrail caps** | Optional per-subscription hourly/daily caps. When a cap is exceeded the task is **not** recorded and an `AnomalyRecord` is created for review. |

## Multiple Subscriptions

When multiple subscriptions are active, each gets its own independent
aggregation bucket. A single `aggregate_and_submit()` call processes all
subscriptions and emits one event per subscription per hour:

```
sub-contoso-001 @ 14:00 → quantity 12
sub-fabrikam-002 @ 14:00 → quantity  5
```

## Extending to Additional Dimensions

The library currently hard-codes the dimension to `task_completed`. If you
need additional dimensions (e.g. `tokens_consumed`), extend the
`MarketplaceMeteringClient` to accept a dimension parameter and register the
new dimension in your Marketplace offer definition in Partner Center.
