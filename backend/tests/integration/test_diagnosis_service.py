import uuid
from datetime import datetime, timezone

from sqlalchemy import text

from app.core.taxonomy import AuditStage, Cause, DiagnosisMethod
from app.models.recovery_case import RecoveryCase
from app.services.diagnosis_service import DIAGNOSIS_CONFIDENCE_THRESHOLD, diagnose_case


def _ingest(api_client, test_merchant, *, decline_code=None, free_text_context=None, amount=2500):
    event_id = f"evt-{uuid.uuid4()}"
    payload = {
        "event_id": event_id,
        "event_type": "payment_failed",
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "free_text_context": free_text_context or "",
            "customer_segment": "consumer",
            "consent_status": "opted_in",
            "channel_history": "[]",
            "geo_region": "South",
            "device_type": "mobile",
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
    return resp.json()["recovery_case_id"]


def test_diagnose_case_uses_rule_based_path_for_known_decline_code(api_client, test_merchant, db):
    case_id = _ingest(api_client, test_merchant, decline_code="EXPIRED_CARD")

    case = db.query(RecoveryCase).filter_by(id=case_id).one()
    diagnosis = diagnose_case(db, case)

    assert diagnosis.cause == Cause.EXPIRED_PAYMENT_METHOD.value
    assert diagnosis.method == DiagnosisMethod.RULE_BASED.value
    assert diagnosis.confidence >= DIAGNOSIS_CONFIDENCE_THRESHOLD


def test_diagnose_case_falls_to_xgboost_for_unmapped_case(api_client, test_merchant, db):
    case_id = _ingest(api_client, test_merchant, decline_code=None, free_text_context="")

    case = db.query(RecoveryCase).filter_by(id=case_id).one()
    diagnosis = diagnose_case(db, case)

    assert diagnosis.method == DiagnosisMethod.XGBOOST.value


def test_diagnose_case_writes_cause_classified_audit_log(api_client, test_merchant, db):
    case_id = _ingest(api_client, test_merchant, decline_code="OTP_FAILED")

    case = db.query(RecoveryCase).filter_by(id=case_id).one()
    diagnosis = diagnose_case(db, case)

    row = db.execute(
        text(
            "SELECT stage, decision FROM audit_logs "
            "WHERE recovery_case_id = :cid AND stage = :stage"
        ),
        {"cid": case_id, "stage": AuditStage.CAUSE_CLASSIFIED.value},
    ).fetchone()
    assert row is not None
    assert row[1] == diagnosis.cause


def test_diagnose_case_writes_human_escalated_log_when_low_confidence(
    api_client, test_merchant, db, monkeypatch
):
    """
    Forces a deterministic low-confidence result via monkeypatch (real
    model confidence varies) to verify the audit-log branch fires
    correctly, since natural low-confidence cases aren't reliably
    reproducible from the trained model's actual distribution.
    """
    import app.services.diagnosis_service as diagnosis_service_module
    from app.schemas.diagnosis import DiagnosisResult

    def _fake_low_confidence(features):
        return DiagnosisResult(
            cause=Cause.UNKNOWN.value,
            confidence=0.1,
            reason="forced low confidence for test",
            signals=[],
            method=DiagnosisMethod.XGBOOST.value,
        )

    monkeypatch.setattr(diagnosis_service_module, "diagnose_from_features", _fake_low_confidence)

    case_id = _ingest(api_client, test_merchant)
    case = db.query(RecoveryCase).filter_by(id=case_id).one()
    diagnosis_service_module.diagnose_case(db, case)

    row = db.execute(
        text(
            "SELECT stage FROM audit_logs WHERE recovery_case_id = :cid AND stage = :stage"
        ),
        {"cid": case_id, "stage": AuditStage.HUMAN_ESCALATED.value},
    ).fetchone()
    assert row is not None
