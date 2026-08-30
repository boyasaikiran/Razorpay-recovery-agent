"""
Tests for Phase 15 security: API key auth and rate limiting.
"""
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.rate_limit import reset_rate_limits
from app.main import app


@pytest.fixture()
def unauthenticated_client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_rate_limits_between_tests():
    reset_rate_limits()
    yield
    reset_rate_limits()


def _event_payload(merchant_id):
    event_id = f"evt-sec-{uuid.uuid4()}"
    return {
        "event_id": event_id,
        "event_type": "payment_failed",
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {},
        "idempotency_key": f"idem-{event_id}",
        "merchant_id": str(merchant_id),
        "amount": 1000,
        "currency": "INR",
        "decline_code": None,
        "attempt_number": 1,
    }


def test_simulate_events_without_api_key_is_rejected(unauthenticated_client, test_merchant):
    resp = unauthenticated_client.post("/api/v1/simulate/events", json=_event_payload(test_merchant))
    assert resp.status_code == 401


def test_simulate_events_with_wrong_api_key_is_rejected(unauthenticated_client, test_merchant):
    resp = unauthenticated_client.post(
        "/api/v1/simulate/events",
        json=_event_payload(test_merchant),
        headers={"X-API-Key": "totally-wrong-key"},
    )
    assert resp.status_code == 401


def test_simulate_events_with_correct_api_key_succeeds(unauthenticated_client, test_merchant):
    settings = get_settings()
    resp = unauthenticated_client.post(
        "/api/v1/simulate/events",
        json=_event_payload(test_merchant),
        headers={"X-API-Key": settings.api_key},
    )
    assert resp.status_code == 201


def test_run_recovery_case_without_api_key_is_rejected(unauthenticated_client, api_client, test_merchant):
    resp = api_client.post("/api/v1/simulate/events", json=_event_payload(test_merchant))
    case_id = resp.json()["recovery_case_id"]

    run_resp = unauthenticated_client.post(f"/api/v1/recovery-cases/{case_id}/run")
    assert run_resp.status_code == 401


def test_evaluation_run_without_api_key_is_rejected(unauthenticated_client):
    resp = unauthenticated_client.post("/api/v1/evaluation/run", params={"n_records": 5})
    assert resp.status_code == 401


def test_read_endpoints_remain_open_without_api_key(unauthenticated_client):
    resp = unauthenticated_client.get("/api/v1/recovery-cases")
    assert resp.status_code == 200
    resp = unauthenticated_client.get("/api/v1/metrics")
    assert resp.status_code == 200
    resp = unauthenticated_client.get("/api/v1/policies")
    assert resp.status_code == 200


def test_auth_fails_safe_when_api_key_not_configured(unauthenticated_client, test_merchant, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "api_key", "")

    resp = unauthenticated_client.post(
        "/api/v1/simulate/events",
        json=_event_payload(test_merchant),
        headers={"X-API-Key": "anything"},
    )
    assert resp.status_code == 503


def test_rate_limit_blocks_after_threshold(unauthenticated_client, test_merchant, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_simulate_events_per_minute", 3)

    responses = [
        unauthenticated_client.post(
            "/api/v1/simulate/events",
            json=_event_payload(test_merchant),
            headers={"X-API-Key": settings.api_key},
        )
        for _ in range(5)
    ]

    statuses = [r.status_code for r in responses]
    assert statuses[:3] == [201, 201, 201]
    assert 429 in statuses[3:]


def test_rate_limit_disabled_flag_bypasses_limiting(unauthenticated_client, test_merchant, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_simulate_events_per_minute", 1)
    monkeypatch.setattr(settings, "rate_limit_enabled", False)

    responses = [
        unauthenticated_client.post(
            "/api/v1/simulate/events",
            json=_event_payload(test_merchant),
            headers={"X-API-Key": settings.api_key},
        )
        for _ in range(3)
    ]
    assert all(r.status_code == 201 for r in responses)
