# End-to-End Quickstart

This quickstart simulates the full agent-task-metering pipeline locally:

1. **Agent tasks complete** — three tasks succeed, one fails.
2. **Evaluate** — each task is checked against the adherence contract.
3. **Record** — only billable tasks are recorded.
4. **Aggregate** — recorded tasks are rolled up into hourly buckets.
5. **Submit (dry-run)** — usage events are printed instead of calling the
   Marketplace API.

## Prerequisites

```bash
pip install -e ".[dev]"
```

## Run

```bash
python examples/quickstart/run_quickstart.py
```

## What to Expect

The script creates four simulated agent tasks for the same subscription and
hour window. Three tasks pass the adherence contract; one fails (empty output).

After aggregation you should see **exactly one** usage event with
`quantity = 3` for the subscription — demonstrating the "one event per hour
per subscription" rule.

Re-running the submission step is a no-op (idempotent), and the duplicate
task is silently ignored.

## Key Concepts Demonstrated

| Concept | Where |
|---|---|
| Intent resolution (required) | Each task provides `query` + `response` evidence |
| Bill outcomes, not attempts | Failed task produces `billable_units = 0` |
| Hourly aggregation | Three tasks → one event with `quantity = 3` |
| Duplicate protection | Re-recording the same task returns `False` |
| Idempotent submission | Re-submitting the same hour window returns `[]` |
| Audit traceability | Correlation IDs printed for every step |
