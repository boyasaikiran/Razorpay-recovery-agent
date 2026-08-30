"""
Integration tests against the real local PostgreSQL database.

Tests use db.flush() (not db.commit()) so the conftest fixture's
rollback cleans up all test data — no residue between test runs.
"""
import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.taxonomy import (
    AuditStage,
    Cause,
    DiagnosisMethod,
    EventType,
    OutcomeStatus,
    PolicyDecision,
    RecoveryAction,
)
from app.models.action import Action
from app.models.audit_log import AuditLog
from app.models.customer import Customer
from app.models.decision import Decision
from app.models.diagnosis import Diagnosis
from app.models.merchant import Merchant
from app.models.model_prediction import ModelPrediction
from app.models.outcome import Outcome
from app.models.payment_event import PaymentEvent
from app.models.recovery_case import RecoveryCase


def _make_merchant(db) -> Merchant:
    merchant = Merchant(name="Test Merchant", email="merchant@example.com")
    db.add(merchant)
    db.flush()
    return merchant


def _make_customer(db, merchant: Merchant) -> Customer:
    customer = Customer(merchant_id=merchant.id, name="Test Customer", email="cust@example.com")
    db.add(customer)
    db.flush()
    return customer


def _make_payment_event(db, merchant: Merchant, customer: Customer, event_id: str) -> PaymentEvent:
    event = PaymentEvent(
        merchant_id=merchant.id,
        customer_id=customer.id,
        event_id=event_id,
        event_type=EventType.PAYMENT_FAILED.value,
        event_timestamp=datetime.now(timezone.utc),
        source="simulated",
        payload={"decline_code": "insufficient_funds"},
        simulation_status=True,
        idempotency_key=f"idem-{event_id}",
        amount=4999,
        currency="INR",
    )
    db.add(event)
    db.flush()
    return event


def test_tables_exist_and_are_queryable(db):
    # A trivial query against every core table proves the schema is live.
    for model in [Merchant, Customer, PaymentEvent, RecoveryCase, Diagnosis,
                  ModelPrediction, Decision, Action, Outcome, AuditLog]:
        result = db.query(model).count()
        assert result >= 0


def test_full_pipeline_chain_can_be_created(db):
    merchant = _make_merchant(db)
    customer = _make_customer(db, merchant)
    event = _make_payment_event(db, merchant, customer, event_id=f"evt-{uuid.uuid4()}")

    case = RecoveryCase(
        merchant_id=merchant.id,
        customer_id=customer.id,
        payment_event_id=event.id,
        case_type=EventType.PAYMENT_FAILED.value,
        amount_at_risk=4999,
        currency="INR",
    )
    db.add(case)
    db.flush()

    diagnosis = Diagnosis(
        recovery_case_id=case.id,
        cause=Cause.INSUFFICIENT_FUNDS.value,
        confidence=0.92,
        method=DiagnosisMethod.RULE_BASED.value,
        reason="decline_code mapped directly to insufficient_funds",
    )
    db.add(diagnosis)
    db.flush()

    prediction = ModelPrediction(
        recovery_case_id=case.id,
        model_name="recovery_probability_xgb",
        model_version="0.1.0",
        recovery_probability=0.71,
    )
    db.add(prediction)
    db.flush()

    decision = Decision(
        recovery_case_id=case.id,
        proposed_action=RecoveryAction.DELAYED_RETRY.value,
        policy_decision=PolicyDecision.APPROVED.value,
        policy_reason="Within retry limits, no risk flag, confidence above threshold.",
    )
    db.add(decision)
    db.flush()

    action = Action(
        decision_id=decision.id,
        recovery_case_id=case.id,
        action_type=RecoveryAction.DELAYED_RETRY.value,
        status="executed",
        simulated=True,
        executed_at=datetime.now(timezone.utc),
    )
    db.add(action)
    db.flush()

    outcome = Outcome(
        action_id=action.id,
        recovery_case_id=case.id,
        status=OutcomeStatus.SUCCESS.value,
        recovered_amount=4999,
        currency="INR",
    )
    db.add(outcome)
    db.flush()

    audit = AuditLog(
        recovery_case_id=case.id,
        stage=AuditStage.OUTCOME_RECORDED.value,
        actor="system",
        decision=OutcomeStatus.SUCCESS.value,
        reason="Delayed retry succeeded.",
        simulation_status=True,
    )
    db.add(audit)
    db.flush()

    # Walk the chain back via relationships to prove FK wiring is correct.
    reloaded_case = db.query(RecoveryCase).filter_by(id=case.id).one()
    assert reloaded_case.payment_event.id == event.id
    assert reloaded_case.diagnoses[0].cause == Cause.INSUFFICIENT_FUNDS.value
    assert reloaded_case.model_predictions[0].recovery_probability == pytest.approx(0.71)
    assert reloaded_case.decisions[0].policy_decision == PolicyDecision.APPROVED.value
    assert reloaded_case.decisions[0].actions[0].outcome.recovered_amount == 4999
    assert reloaded_case.audit_logs[0].stage == AuditStage.OUTCOME_RECORDED.value


def test_duplicate_event_id_is_rejected(db):
    merchant = _make_merchant(db)
    customer = _make_customer(db, merchant)
    shared_event_id = f"evt-dup-{uuid.uuid4()}"

    _make_payment_event(db, merchant, customer, event_id=shared_event_id)

    dup = PaymentEvent(
        merchant_id=merchant.id,
        customer_id=customer.id,
        event_id=shared_event_id,  # same event_id -> should violate unique constraint
        event_type=EventType.PAYMENT_FAILED.value,
        event_timestamp=datetime.now(timezone.utc),
        source="simulated",
        payload={},
        simulation_status=True,
        idempotency_key=f"idem-other-{uuid.uuid4()}",
    )
    db.add(dup)
    with pytest.raises(IntegrityError):
        db.flush()


def test_duplicate_idempotency_key_is_rejected(db):
    merchant = _make_merchant(db)
    customer = _make_customer(db, merchant)
    shared_key = f"idem-dup-{uuid.uuid4()}"

    e1 = PaymentEvent(
        merchant_id=merchant.id,
        customer_id=customer.id,
        event_id=f"evt-{uuid.uuid4()}",
        event_type=EventType.PAYMENT_FAILED.value,
        event_timestamp=datetime.now(timezone.utc),
        source="simulated",
        payload={},
        simulation_status=True,
        idempotency_key=shared_key,
    )
    db.add(e1)
    db.flush()

    e2 = PaymentEvent(
        merchant_id=merchant.id,
        customer_id=customer.id,
        event_id=f"evt-{uuid.uuid4()}",
        event_type=EventType.PAYMENT_FAILED.value,
        event_timestamp=datetime.now(timezone.utc),
        source="simulated",
        payload={},
        simulation_status=True,
        idempotency_key=shared_key,  # duplicate
    )
    db.add(e2)
    with pytest.raises(IntegrityError):
        db.flush()


def test_recovery_case_requires_valid_payment_event_fk(db):
    merchant = _make_merchant(db)
    bogus_event_id = uuid.uuid4()

    case = RecoveryCase(
        merchant_id=merchant.id,
        payment_event_id=bogus_event_id,  # does not exist
        case_type=EventType.PAYMENT_FAILED.value,
    )
    db.add(case)
    with pytest.raises(IntegrityError):
        db.flush()


def test_invoice_can_be_created_with_days_overdue(db):
    merchant = _make_merchant(db)
    customer = _make_customer(db, merchant)

    from app.models.invoice import Invoice

    invoice = Invoice(
        merchant_id=merchant.id,
        customer_id=customer.id,
        amount=15000,
        currency="INR",
        due_date=date(2026, 6, 1),
        days_overdue=45,
        status="overdue",
    )
    db.add(invoice)
    db.flush()

    reloaded = db.query(Invoice).filter_by(id=invoice.id).one()
    assert reloaded.days_overdue == 45
    assert reloaded.status == "overdue"
