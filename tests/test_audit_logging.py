"""Unit tests for audit logging, correlation IDs, guardrails, and anomaly detection."""

import json
from datetime import datetime, timezone

from agent_task_metering.audit_logger import AuditLogger, get_audit_logger
from agent_task_metering.metering.client import (
    AnomalyRecord,
    GuardrailConfig,
    MarketplaceMeteringClient,
)

# ---- AuditLogger ----------------------------------------------------------


def test_audit_logger_emits_json(capfd):
    """AuditLogger.log_event() emits a JSON line to stderr."""
    logger = AuditLogger("test.audit.json")
    logger.log_event("test_event", correlation_id="cid-1", extra_key="val")
    captured = capfd.readouterr()
    line = captured.err.strip()
    payload = json.loads(line)
    assert payload["event"] == "test_event"
    assert payload["correlation_id"] == "cid-1"
    assert payload["extra_key"] == "val"
    assert "timestamp" in payload


def test_audit_logger_returns_payload():
    """log_event returns the structured payload dict."""
    logger = AuditLogger("test.audit.returns")
    result = logger.log_event("ev", correlation_id="c1", foo="bar")
    assert result["event"] == "ev"
    assert result["correlation_id"] == "c1"
    assert result["foo"] == "bar"


def test_get_audit_logger_returns_instance():
    assert isinstance(get_audit_logger(), AuditLogger)


# ---- GuardrailConfig defaults --------------------------------------------


def test_guardrail_config_defaults():
    cfg = GuardrailConfig()
    assert cfg.hourly_cap == 0
    assert cfg.daily_cap == 0


# ---- Hourly cap -----------------------------------------------------------


def test_hourly_cap_blocks_after_limit():
    """Once hourly cap is hit, further recordings are rejected."""
    client = MarketplaceMeteringClient(
        dry_run=True,
        guardrail_config=GuardrailConfig(hourly_cap=3),
    )
    ts = datetime(2025, 6, 1, 14, 10, 0, tzinfo=timezone.utc)

    assert client.record_task_completed("sub-1", "t1", ts) is True
    assert client.record_task_completed("sub-1", "t2", ts) is True
    assert client.record_task_completed("sub-1", "t3", ts) is True
    # 4th should be rejected
    assert client.record_task_completed("sub-1", "t4", ts) is False


def test_hourly_cap_creates_anomaly_record():
    """Exceeding hourly cap creates an AnomalyRecord."""
    client = MarketplaceMeteringClient(
        dry_run=True,
        guardrail_config=GuardrailConfig(hourly_cap=2),
    )
    ts = datetime(2025, 6, 1, 14, 10, 0, tzinfo=timezone.utc)

    client.record_task_completed("sub-1", "t1", ts)
    client.record_task_completed("sub-1", "t2", ts)
    client.record_task_completed("sub-1", "t3", ts, correlation_id="cid-3")

    anomalies = client.anomalies
    assert len(anomalies) == 1
    a = anomalies[0]
    assert a.subscription_ref == "sub-1"
    assert a.cap_type == "hourly"
    assert a.cap_value == 2
    assert a.task_id == "t3"
    assert a.correlation_id == "cid-3"


def test_hourly_cap_different_subscriptions_independent():
    """Caps are per-subscription; one hitting cap doesn't affect another."""
    client = MarketplaceMeteringClient(
        dry_run=True,
        guardrail_config=GuardrailConfig(hourly_cap=1),
    )
    ts = datetime(2025, 6, 1, 14, 0, 0, tzinfo=timezone.utc)

    assert client.record_task_completed("sub-A", "t1", ts) is True
    assert client.record_task_completed("sub-A", "t2", ts) is False  # capped
    assert client.record_task_completed("sub-B", "t3", ts) is True  # different sub


def test_hourly_cap_different_hours_independent():
    """Tasks in different hour windows don't share the cap."""
    client = MarketplaceMeteringClient(
        dry_run=True,
        guardrail_config=GuardrailConfig(hourly_cap=1),
    )
    ts1 = datetime(2025, 6, 1, 14, 0, 0, tzinfo=timezone.utc)
    ts2 = datetime(2025, 6, 1, 15, 0, 0, tzinfo=timezone.utc)

    assert client.record_task_completed("sub-1", "t1", ts1) is True
    assert client.record_task_completed("sub-1", "t2", ts1) is False  # capped
    assert client.record_task_completed("sub-1", "t3", ts2) is True  # new hour


# ---- Daily cap ------------------------------------------------------------


def test_daily_cap_blocks_after_limit():
    """Once daily cap is hit, further recordings (across hours) are rejected."""
    client = MarketplaceMeteringClient(
        dry_run=True,
        guardrail_config=GuardrailConfig(daily_cap=2),
    )
    ts1 = datetime(2025, 6, 1, 14, 0, 0, tzinfo=timezone.utc)
    ts2 = datetime(2025, 6, 1, 15, 0, 0, tzinfo=timezone.utc)

    assert client.record_task_completed("sub-1", "t1", ts1) is True
    assert client.record_task_completed("sub-1", "t2", ts2) is True
    # 3rd task hits daily cap
    assert client.record_task_completed("sub-1", "t3", ts2) is False


def test_daily_cap_creates_anomaly_record():
    """Exceeding daily cap creates an AnomalyRecord with cap_type='daily'."""
    client = MarketplaceMeteringClient(
        dry_run=True,
        guardrail_config=GuardrailConfig(daily_cap=1),
    )
    ts = datetime(2025, 6, 1, 14, 0, 0, tzinfo=timezone.utc)

    client.record_task_completed("sub-1", "t1", ts)
    client.record_task_completed("sub-1", "t2", ts, correlation_id="daily-cid")

    anomalies = client.anomalies
    assert len(anomalies) == 1
    assert anomalies[0].cap_type == "daily"
    assert anomalies[0].correlation_id == "daily-cid"


def test_daily_cap_different_days_independent():
    """Tasks on different days don't share the cap."""
    client = MarketplaceMeteringClient(
        dry_run=True,
        guardrail_config=GuardrailConfig(daily_cap=1),
    )
    ts1 = datetime(2025, 6, 1, 14, 0, 0, tzinfo=timezone.utc)
    ts2 = datetime(2025, 6, 2, 14, 0, 0, tzinfo=timezone.utc)

    assert client.record_task_completed("sub-1", "t1", ts1) is True
    assert client.record_task_completed("sub-1", "t2", ts1) is False  # capped
    assert client.record_task_completed("sub-1", "t3", ts2) is True  # new day


# ---- Correlation ID propagation -------------------------------------------


def test_correlation_id_propagated_in_recording():
    """correlation_id passes through to structured log payloads."""
    logger = AuditLogger("test.correlation")
    payload = logger.log_event(
        "task_recorded", correlation_id="trace-abc", task_id="t1"
    )
    assert payload["correlation_id"] == "trace-abc"
    assert payload["task_id"] == "t1"


# ---- AnomalyRecord -------------------------------------------------------


def test_anomaly_record_to_dict():
    a = AnomalyRecord(
        subscription_ref="sub-1",
        cap_type="hourly",
        cap_value=10,
        actual_value=10,
        task_id="t99",
        correlation_id="cid-99",
    )
    d = a.to_dict()
    assert d["subscription_ref"] == "sub-1"
    assert d["cap_type"] == "hourly"
    assert d["cap_value"] == 10
    assert d["task_id"] == "t99"
    assert isinstance(d["timestamp"], str)


# ---- Zero caps (unlimited) -----------------------------------------------


def test_zero_caps_means_unlimited():
    """hourly_cap=0, daily_cap=0 means no limits."""
    client = MarketplaceMeteringClient(
        dry_run=True,
        guardrail_config=GuardrailConfig(hourly_cap=0, daily_cap=0),
    )
    ts = datetime(2025, 6, 1, 14, 0, 0, tzinfo=timezone.utc)
    for i in range(50):
        assert client.record_task_completed("sub-1", f"t{i}", ts) is True
    assert len(client.anomalies) == 0


# ---- Both caps active -----------------------------------------------------


def test_hourly_cap_checked_before_daily_cap():
    """When both caps are active, hourly is checked first."""
    client = MarketplaceMeteringClient(
        dry_run=True,
        guardrail_config=GuardrailConfig(hourly_cap=2, daily_cap=100),
    )
    ts = datetime(2025, 6, 1, 14, 0, 0, tzinfo=timezone.utc)

    client.record_task_completed("sub-1", "t1", ts)
    client.record_task_completed("sub-1", "t2", ts)
    assert client.record_task_completed("sub-1", "t3", ts) is False
    assert client.anomalies[0].cap_type == "hourly"


# ---- Existing behavior unchanged with guardrails --------------------------


def test_aggregation_still_works_with_caps():
    """Guardrails don't interfere with normal aggregation."""
    client = MarketplaceMeteringClient(
        dry_run=True,
        guardrail_config=GuardrailConfig(hourly_cap=10),
    )
    ts = datetime(2025, 6, 1, 14, 0, 0, tzinfo=timezone.utc)
    for i in range(5):
        client.record_task_completed("sub-1", f"t{i}", ts)

    events = client.aggregate_and_submit("2025-06-01T14:00:00Z")
    assert len(events) == 1
    assert events[0].quantity == 5


def test_duplicate_still_rejected_before_cap_check():
    """Duplicates are still caught before cap enforcement."""
    client = MarketplaceMeteringClient(
        dry_run=True,
        guardrail_config=GuardrailConfig(hourly_cap=2),
    )
    ts = datetime(2025, 6, 1, 14, 0, 0, tzinfo=timezone.utc)

    assert client.record_task_completed("sub-1", "t1", ts) is True
    assert client.record_task_completed("sub-1", "t1", ts) is False  # dup, not cap
    assert len(client.anomalies) == 0  # no anomaly for dup
