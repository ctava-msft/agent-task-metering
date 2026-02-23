"""Unit tests for TaskRecord model."""

from datetime import datetime

from agent_task_metering.models import TaskRecord


def test_task_record_defaults():
    record = TaskRecord(task_id="t1", agent_id="a1", task_type="chat")
    assert record.task_id == "t1"
    assert record.agent_id == "a1"
    assert record.task_type == "chat"
    assert record.input_tokens == 0
    assert record.output_tokens == 0
    assert record.end_time is None
    assert record.metadata == {}


def test_total_tokens():
    record = TaskRecord(
        task_id="t2", agent_id="a1", task_type="chat",
        input_tokens=100, output_tokens=50,
    )
    assert record.total_tokens == 150


def test_duration_seconds_none_when_not_complete():
    record = TaskRecord(task_id="t3", agent_id="a1", task_type="chat")
    assert record.duration_seconds is None


def test_duration_seconds():
    start = datetime(2025, 1, 1, 0, 0, 0)
    end = datetime(2025, 1, 1, 0, 0, 30)
    record = TaskRecord(task_id="t4", agent_id="a1", task_type="chat",
                        start_time=start, end_time=end)
    assert record.duration_seconds == 30.0
