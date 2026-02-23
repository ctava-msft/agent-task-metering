# Marketplace Packaging Checklist

Use this checklist when preparing to publish (or update) an Azure Marketplace
SaaS offer that uses `agent-task-metering` for metered billing.

## Partner Center Configuration

- [ ] **Create / update the SaaS offer** in
      [Partner Center](https://partner.microsoft.com/dashboard/marketplace-offers/overview).
- [ ] **Define a plan** with at least one custom metering dimension:
  - Dimension ID: `task_completed`
  - Display name: *Task Completed*
  - Unit of measure: *Task*
- [ ] **Set the pricing model** (flat-rate + overage, per-unit, or free +
      metered). The `task_completed` dimension is the metered overage
      component.
- [ ] **Configure the landing page** and webhook URLs if using SaaS
      fulfillment APIs.
- [ ] **Register the AAD application** used for Marketplace API
      authentication (client credentials flow).

## Code Integration

- [ ] Set `plan_id` on `MarketplaceMeteringClient` to match the plan ID
      defined in Partner Center.
- [ ] Provide a `submit_callback` that calls the
      [Marketplace Metered Billing API](https://learn.microsoft.com/azure/marketplace/marketplace-metering-service-apis)
      (POST `https://marketplaceapi.microsoft.com/api/usageEvent`).
- [ ] Set `dry_run=False` when ready to submit real usage events.
- [ ] Wire up the control plane to call `evaluate → record → aggregate →
      submit` on each task completion (see
      [`docs/ARCHITECTURE.md`](ARCHITECTURE.md)).
- [ ] Configure `GuardrailConfig` with sensible hourly/daily caps for your
      workload.

## Testing

- [ ] Run the end-to-end quickstart (`examples/quickstart/run_quickstart.py`)
      in dry-run mode and verify output.
- [ ] Validate that duplicate tasks are not double-billed.
- [ ] Confirm that failed tasks produce `billable_units = 0`.
- [ ] Test guardrail caps — exceed the cap and verify that
      `AnomalyRecord` entries are created.
- [ ] Review audit log output for correlation-ID traceability.

## Submission

- [ ] Run `make lint && make test` — all checks must pass.
- [ ] Publish the offer (or submit for review) in Partner Center.
- [ ] Smoke-test with a test subscription using the Marketplace
      [test publisher](https://learn.microsoft.com/azure/marketplace/test-saas-overview)
      flow.

## References

- [Azure Marketplace Metered Billing APIs](https://learn.microsoft.com/azure/marketplace/marketplace-metering-service-apis)
- [SaaS fulfillment APIs](https://learn.microsoft.com/azure/marketplace/partner-center-portal/pc-saas-fulfillment-apis)
- [Mastering the Marketplace](https://microsoft.github.io/Mastering-the-Marketplace/)
- [microsoft/metered-billing-accelerator](https://github.com/microsoft/metered-billing-accelerator)
- [microsoft/commercial-marketplace-solutions](https://github.com/microsoft/commercial-marketplace-solutions)
