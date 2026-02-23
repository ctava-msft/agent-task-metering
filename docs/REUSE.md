# Reuse Documentation

This document describes which patterns in the `agent-task-metering` metering
module were **reused** from established Microsoft references and what is
**custom** to this project.

---

## Reused Patterns

| Pattern | Source | How it is applied |
|---|---|---|
| **Hourly aggregation** | [microsoft/metered-billing-accelerator](https://github.com/microsoft/metered-billing-accelerator) — accounting & aggregation engine | The `MarketplaceMeteringClient` buckets every `record_task_completed()` call into UTC hour windows and emits **one** usage event per subscription per hour with the aggregated quantity. |
| **Idempotency / duplicate protection** | metered-billing-accelerator + [Marketplace Metered Billing API constraints](https://learn.microsoft.com/azure/marketplace/marketplace-metering-service-apis) | Each `(subscription_ref, task_id, hour)` triple is tracked in a set. A second call with the same triple is silently ignored, ensuring no task is billed twice within the same hour. Submitted windows are also tracked so that `aggregate_and_submit()` is safe to call repeatedly. |
| **Single-dimension metering** | [microsoft/commercial-marketplace-solutions](https://github.com/microsoft/commercial-marketplace-solutions) — SaaS metered-engine samples | The dimension is hard-coded to `task_completed` to avoid dimension explosion, matching the Marketplace best practice of using a small, fixed set of custom meter dimensions. |
| **Usage event payload format** | [Azure Marketplace Metered Billing API](https://learn.microsoft.com/azure/marketplace/marketplace-metering-service-apis) | `UsageEvent` mirrors the API schema: `resourceId`, `quantity`, `dimension`, `effectiveStartTime`, and `planId`. |
| **Dry-run / testability** | General SaaS accelerator testing patterns | `MarketplaceMeteringClient(dry_run=True)` prints the JSON payload instead of calling the Marketplace API, enabling local testing and CI validation without credentials. |

## Custom to This Project

| Component | Description |
|---|---|
| `record_task_completed()` | Thin recording API tailored to agent task completions (wraps the aggregation logic above). |
| In-memory store | Completions are held in a Python `dict[tuple, set]` for simplicity. A production deployment would replace this with a durable store (e.g., database, Redis). |
| `submit_callback` hook | Allows callers to inject the real Marketplace HTTP call (or any other side-effect) without coupling the library to a specific HTTP client. |
| `pending_quantity()` helper | Introspection method for debugging and testing. |

## References

1. **microsoft/metered-billing-accelerator** — <https://github.com/microsoft/metered-billing-accelerator>
2. **microsoft/commercial-marketplace-solutions** — <https://github.com/microsoft/commercial-marketplace-solutions>
3. **Azure Marketplace Metered Billing APIs** — <https://learn.microsoft.com/azure/marketplace/marketplace-metering-service-apis>
4. **Mastering the Marketplace** — <https://microsoft.github.io/Mastering-the-Marketplace/>
