# Architecture

This document describes how `agent-task-metering` fits into a Marketplace-enabled
agent platform and how it pairs with an **Azure Agents Control Plane**.

## High-Level Flow

```
┌─────────────────────┐
│   Agent Runtime      │  (your agent completes a task)
└────────┬────────────┘
         │ task outputs + evidence
         ▼
┌─────────────────────────────────────┐
│  agent-task-metering                │
│                                     │
│  1. Evaluate (adherence contract)   │  ← deterministic gates
│  2. Record   (task_completed)       │  ← if billable
│  3. Aggregate (hourly buckets)      │  ← one event per sub per hour
│  4. Submit   (Marketplace API)      │  ← or dry-run
└────────┬────────────────────────────┘
         │ UsageEvent
         ▼
┌─────────────────────────────────────┐
│  Azure Marketplace Metered Billing  │
│  (Partner Center / Commerce)        │
└─────────────────────────────────────┘
```

## Components

### 1. Task Adherence Evaluator

The `TaskAdherenceEvaluator` runs five sequential **deterministic gates** that
decide whether a completed task is billable:

| Gate | Name | Required? | Description |
|------|------|-----------|-------------|
| 0 | Intent resolution | Optional | User intent was identified and resolved |
| 1 | Terminal success | Yes | Task reached a terminal success state |
| 2 | Required outputs | Configurable | All configured output keys are present |
| 3 | Output validation | Yes | Output values are non-null / non-empty |
| 4 | Approval | Optional | Explicit `approved` flag is truthy |

A task is billable (`billable_units = 1`) only when **both** intent resolution
and adherence gates pass. This enforces the principle of
**billing outcomes, not attempts** — failed or incomplete tasks are never billed.

### 2. Marketplace Metering Client

`MarketplaceMeteringClient` records billable task completions and aggregates
them into usage events that conform to the
[Azure Marketplace Metered Billing API](https://learn.microsoft.com/azure/marketplace/marketplace-metering-service-apis):

- **Hourly aggregation** — one usage event per subscription per hour with the
  aggregated quantity.
- **Single dimension** — the hard-coded dimension is `task_completed`.
- **Idempotency** — duplicate `(subscription, task_id, hour)` triples are
  silently ignored.
- **Guardrails** — configurable hourly/daily caps per subscription to prevent
  anomalous billing.

### 3. Audit Trail

Every evaluation decision and metering event carries a **correlation ID** that
threads through the full pipeline:

```
evaluation_decision → task_recorded → aggregation_complete → marketplace_submission
```

See [`docs/audit-logging.md`](audit-logging.md) for the structured logging
schema and how to query "what got billed and why."

## Pairing with Azure Agents Control Plane

In a production deployment the control plane is responsible for:

| Responsibility | Control Plane | agent-task-metering |
|---|---|---|
| Agent orchestration & task dispatch | ✅ | — |
| Task output collection | ✅ | — |
| Adherence evaluation (billable?) | — | ✅ |
| Metering aggregation & submission | — | ✅ |
| Subscription & plan management | ✅ | — |
| Guardrail anomaly alerting | — | ✅ (logs + records) |
| Audit / billing reconstruction | — | ✅ |

The control plane calls `agent-task-metering` after every completed task to:

1. **Evaluate** — pass the task evidence through the adherence contract.
2. **Record** — if billable, record a `task_completed` event.
3. **Aggregate & Submit** — on a schedule (e.g. once per hour), aggregate
   recorded completions and submit usage events to the Marketplace API.

This separation keeps billing logic isolated, testable, and
dispute-resistant — the control plane never directly emits billing events.

## Deployment Options

| Option | Description |
|---|---|
| **In-process library** | Import `agent_task_metering` directly in the control plane process. Simplest option for single-instance deployments. |
| **Sidecar / microservice** | Run the REST API (`python -m agent_task_metering.evaluation.api`) as a sidecar. Good for polyglot architectures or when you want independent scaling. |
| **Container** | Build with `make build` (uses `src/Dockerfile`). Deploy alongside the control plane in the same pod or as a separate service. |
