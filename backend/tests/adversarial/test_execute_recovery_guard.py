"""
Tests for tool_execute_recovery's structural guard: the single most
safety-critical piece of code in this codebase. If this guard fails,
the "LLM proposes, policy engine disposes" principle is not actually
enforced -- it would just be a comment.
"""
import uuid
from datetime import datetime, timezone

import pytest

from app.agents.tools import ExecutionNotApprovedError, tool_execute_recovery
from app.core.taxonomy import PolicyDecision
from app.models.action import Action
from app.models.decision import Decision
from app.models.recovery_case import RecoveryCase


def _real_case_id(api_client, test_merchant, db) -> uuid.UUID:
    """A genuine, DB-valid recovery_case -- so the guard's own behavior
    is what's under test, not incidentally masked by an FK violation
    on a fabricated case_id."""
    event_id = f"evt-{uuid.uuid4()}"
    resp = api_client.post(
        "/api/v1/simulate/events",
        json={
            "event_id": event_id,
            "event_type": "payment_failed",
            "event_timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": {},
            "idempotency_key": f"idem-{event_id}",
            "merchant_id": str(test_merchant),
            "amount": 1000,
            "currency": "INR",
            "decline_code": None,
            "attempt_number": 1,
        },
    )
    return uuid.UUID(resp.json()["recovery_case_id"])


def _fake_decision(policy_decision: str, case_id: uuid.UUID) -> Decision:
    """A Decision-shaped object NOT persisted to the DB -- proves the
    guard checks the field value itself, not some DB-side trigger."""
    return Decision(
        id=uuid.uuid4(),
        recovery_case_id=case_id,
        proposed_action="RETRY_PAYMENT",
        policy_decision=policy_decision,
        policy_reason="test",
    )


def test_execute_refuses_denied_decision(api_client, test_merchant, db):
    case_id = _real_case_id(api_client, test_merchant, db)
    fake = _fake_decision(PolicyDecision.DENIED.value, case_id)
    with pytest.raises(ExecutionNotApprovedError):
        tool_execute_recovery(db, fake)


def test_execute_refuses_route_to_human_decision(api_client, test_merchant, db):
    case_id = _real_case_id(api_client, test_merchant, db)
    fake = _fake_decision(PolicyDecision.ROUTE_TO_HUMAN.value, case_id)
    with pytest.raises(ExecutionNotApprovedError):
        tool_execute_recovery(db, fake)


def test_execute_refuses_tampered_arbitrary_string(api_client, test_merchant, db):
    """
    Even a value that isn't a real PolicyDecision at all (e.g. a
    forged/corrupted field) must be refused -- the guard is an
    equality check against APPROVED specifically, not merely "not
    DENIED".
    """
    case_id = _real_case_id(api_client, test_merchant, db)
    fake = _fake_decision("TOTALLY_MADE_UP_VALUE", case_id)
    with pytest.raises(ExecutionNotApprovedError):
        tool_execute_recovery(db, fake)


def test_execute_refuses_empty_string(api_client, test_merchant, db):
    case_id = _real_case_id(api_client, test_merchant, db)
    fake = _fake_decision("", case_id)
    with pytest.raises(ExecutionNotApprovedError):
        tool_execute_recovery(db, fake)


def test_refused_execution_creates_no_action_row(api_client, test_merchant, db):
    case_id = _real_case_id(api_client, test_merchant, db)
    fake = _fake_decision(PolicyDecision.DENIED.value, case_id)
    count_before = db.query(Action).count()
    with pytest.raises(ExecutionNotApprovedError):
        tool_execute_recovery(db, fake)
    count_after = db.query(Action).count()
    assert count_after == count_before


def test_forged_decision_with_random_nonexistent_case_id_is_rejected_at_db_level(db):
    """
    Defense in depth, layer 2: even a completely fabricated Decision
    pointing at a recovery_case_id that doesn't exist in the DB at all
    fails at the database FK constraint level the moment any write is
    attempted -- it can never masquerade as a real approved case.
    """
    from sqlalchemy.exc import IntegrityError

    fake = _fake_decision(PolicyDecision.APPROVED.value, uuid.uuid4())
    with pytest.raises(IntegrityError):
        tool_execute_recovery(db, fake)
    db.rollback()
