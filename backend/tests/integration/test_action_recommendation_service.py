import uuid
from datetime import datetime, timezone

from sqlalchemy import text

from app.core.taxonomy import AuditStage
from app.models.recovery_case import RecoveryCase
from app.services.action_recommendation_service import recommend_action_for_case
from app.services.diagnosis_service import diagnose_case
from app.services.recovery_probability_service import predict_for_case


def test_full_pipeline_through_action_recommendation(api_client, test_merchant, db):
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
        },
        "idempotency_key": f"idem-{event_id}",
        "merchant_id": str(test_merchant),
        "amount": 1800,
        "currency": "INR",
        "payment_method": "card",
        "decline_code": "EXPIRED_CARD",
        "attempt_number": 1,
    }
    resp = api_client.post("/api/v1/simulate/events", json=payload)
    case_id = resp.json()["recovery_case_id"]

    case = db.query(RecoveryCase).filter_by(id=case_id).one()
    diagnosis = diagnose_case(db, case)
    prediction = predict_for_case(db, case, diagnosis)
    recommendation = recommend_action_for_case(db, case, diagnosis, prediction)

    assert recommendation.action == "CREATE_PAYMENT_LINK"

    row = db.execute(
        text("SELECT stage, decision FROM audit_logs WHERE recovery_case_id = :cid AND stage = :stage"),
        {"cid": case_id, "stage": AuditStage.ACTION_PROPOSED.value},
    ).fetchone()
    assert row is not None
    assert row[1] == "CREATE_PAYMENT_LINK"
