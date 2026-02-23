"""Unit tests for TaskMeter."""

from datetime import datetime

from agent_task_metering.meter import TaskMeter


def test_record_and_summary():
    meter = TaskMeter()
    meter.record("t1", "agent-A", "chat", input_tokens=10, output_tokens=5)
    meter.record("t2", "agent-B", "search", input_tokens=20, output_tokens=10)

    summary = meter.summary()
    assert summary["total_tasks"] == 2
    assert summary["total_tokens"] == 45
    assert set(summary["agents"]) == {"agent-A", "agent-B"}


def test_records_for_agent():
    meter = TaskMeter()
    meter.record("t1", "agent-A", "chat", input_tokens=10, output_tokens=5)
    meter.record("t2", "agent-A", "search", input_tokens=20, output_tokens=10)
    meter.record("t3", "agent-B", "chat", input_tokens=5, output_tokens=3)

    records = meter.records_for_agent("agent-A")
    assert len(records) == 2
    assert all(r.agent_id == "agent-A" for r in records)


def test_total_tokens_empty():
    meter = TaskMeter()
    assert meter.total_tokens() == 0


def test_record_with_timestamps():
    meter = TaskMeter()
    start = datetime(2025, 1, 1, 0, 0, 0)
    end = datetime(2025, 1, 1, 0, 1, 0)
    record = meter.record(
        "t1", "agent-A", "chat",
        input_tokens=10, output_tokens=5,
        start_time=start, end_time=end,
    )
    assert record.duration_seconds == 60.0


def test_summary_empty():
    meter = TaskMeter()
    summary = meter.summary()
    assert summary["total_tasks"] == 0
    assert summary["total_tokens"] == 0
    assert summary["agents"] == []
