import uuid
from datetime import datetime, timezone

from sqlalchemy import text

from app.core.taxonomy import AuditStage
from app.models.diagnosis import Diagnosis
from app.models.recovery_case import RecoveryCase
from app.services.diagnosis_service import diagnose_case
from app.services.recovery_probability_service import predict_for_case


def _ingest_and_diagnose(api_client, test_merchant, db, *, decline_code=None, amount=2500):
    event_id = f"evt-{uuid.uuid4()}"
    payload = {
        "event_id": event_id,
        "event_type": "payment_failed",
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "customer_segment": "consumer",
            "consent_status": "opted_in",
            "channel_history": "[]",
            "geo_region": "South",
            "device_type": "mobile",
            "customer_lifetime_value": 6000,
            "previous_recovery_rate": 0.35,
        },
        "idempotency_key": f"idem-{event_id}",
        "merchant_id": str(test_merchant),
        "amount": amount,
        "currency": "INR",
        "payment_method": "card",
        "decline_code": decline_code,
        "attempt_number": 1,
    }
    resp = api_client.post("/api/v1/simulate/events", json=payload)
    assert resp.status_code == 201
    case_id = resp.json()["recovery_case_id"]

    case = db.query(RecoveryCase).filter_by(id=case_id).one()
    diagnosis = diagnose_case(db, case)
    return case, diagnosis


def test_predict_for_case_creates_model_prediction(api_client, test_merchant, db):
    case, diagnosis = _ingest_and_diagnose(api_client, test_merchant, db, decline_code="ISSUER_UNAVAILABLE")

    prediction = predict_for_case(db, case, diagnosis)

    assert prediction.recovery_probability is not None
    assert 0.0 <= prediction.recovery_probability <= 1.0
    assert prediction.model_name == "recovery_probability_xgb"


def test_predict_for_case_writes_recovery_predicted_audit_log(api_client, test_merchant, db):
    case, diagnosis = _ingest_and_diagnose(api_client, test_merchant, db, decline_code="EXPIRED_CARD")

    prediction = predict_for_case(db, case, diagnosis)

    row = db.execute(
        text("SELECT stage, decision FROM audit_logs WHERE recovery_case_id = :cid AND stage = :stage"),
        {"cid": case.id, "stage": AuditStage.RECOVERY_PREDICTED.value},
    ).fetchone()
    assert row is not None
    assert f"{prediction.recovery_probability:.4f}" in row[1]


def test_predict_for_case_stores_feature_snapshot(api_client, test_merchant, db):
    case, diagnosis = _ingest_and_diagnose(api_client, test_merchant, db, decline_code="NSF")

    prediction = predict_for_case(db, case, diagnosis)

    assert prediction.feature_snapshot is not None
    assert "customer_lifetime_value" in prediction.feature_snapshot
