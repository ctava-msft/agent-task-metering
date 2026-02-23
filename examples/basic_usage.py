"""Example: basic usage of agent-task-metering."""

from agent_task_metering import TaskMeter

meter = TaskMeter()

# Record some agent tasks
meter.record("task-001", "gpt-4o-agent", "chat", input_tokens=512, output_tokens=128)
meter.record("task-002", "gpt-4o-agent", "search", input_tokens=64, output_tokens=32)
meter.record("task-003", "phi-3-agent", "summarize", input_tokens=1024, output_tokens=256)

# Print a summary
summary = meter.summary()
print(f"Total tasks : {summary['total_tasks']}")
print(f"Total tokens: {summary['total_tokens']}")
print(f"Agents seen : {summary['agents']}")

# Per-agent breakdown
for agent_id in summary["agents"]:
    records = meter.records_for_agent(agent_id)
    tokens = sum(r.total_tokens for r in records)
    print(f"  {agent_id}: {len(records)} task(s), {tokens} tokens")
