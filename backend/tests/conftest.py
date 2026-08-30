import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.main import app


@pytest.fixture()
def db() -> Session:
    """
    Yields a real SQLAlchemy session against the local test database.
    Each test runs inside a transaction that is rolled back afterward
    (tests must use db.flush(), never db.commit(), to keep this true).
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def api_client() -> TestClient:
    """
    Sends X-API-Key automatically for every request in this test suite
    (reads the same API_KEY the app itself uses via settings) -- Phase 15
    added real authentication to state-changing endpoints, and this
    fixture is what keeps the rest of the test suite exercising those
    endpoints without every single test needing to know about auth.
    Tests that specifically verify auth behavior override this by
    building their own TestClient or omitting the header explicitly.
    """
    from app.core.config import get_settings

    settings = get_settings()
    client = TestClient(app)
    if settings.api_key:
        client.headers.update({"X-API-Key": settings.api_key})
    return client


@pytest.fixture()
def test_merchant():
    """
    Creates a merchant for API-level tests that go through service code
    which commits internally (e.g. ingestion). Since those commits are
    real, teardown explicitly deletes everything created under this
    merchant, in FK-safe order, instead of relying on rollback.
    """
    session = SessionLocal()
    merchant_id = uuid.uuid4()
    session.execute(
        text(
            "INSERT INTO merchants (id, name, email, created_at) "
            "VALUES (:id, :name, :email, now())"
        ),
        {"id": merchant_id, "name": "API Test Merchant", "email": f"{merchant_id}@example.com"},
    )
    session.commit()

    yield merchant_id

    session.execute(
        text(
            "DELETE FROM audit_logs WHERE recovery_case_id IN "
            "(SELECT id FROM recovery_cases WHERE merchant_id = :mid)"
        ),
        {"mid": merchant_id},
    )
    session.execute(
        text(
            "DELETE FROM outcomes WHERE recovery_case_id IN "
            "(SELECT id FROM recovery_cases WHERE merchant_id = :mid)"
        ),
        {"mid": merchant_id},
    )
    session.execute(
        text(
            "DELETE FROM actions WHERE recovery_case_id IN "
            "(SELECT id FROM recovery_cases WHERE merchant_id = :mid)"
        ),
        {"mid": merchant_id},
    )
    session.execute(
        text(
            "DELETE FROM decisions WHERE recovery_case_id IN "
            "(SELECT id FROM recovery_cases WHERE merchant_id = :mid)"
        ),
        {"mid": merchant_id},
    )
    session.execute(
        text(
            "DELETE FROM model_predictions WHERE recovery_case_id IN "
            "(SELECT id FROM recovery_cases WHERE merchant_id = :mid)"
        ),
        {"mid": merchant_id},
    )
    session.execute(
        text(
            "DELETE FROM diagnoses WHERE recovery_case_id IN "
            "(SELECT id FROM recovery_cases WHERE merchant_id = :mid)"
        ),
        {"mid": merchant_id},
    )
    session.execute(text("DELETE FROM recovery_cases WHERE merchant_id = :mid"), {"mid": merchant_id})
    session.execute(text("DELETE FROM payment_events WHERE merchant_id = :mid"), {"mid": merchant_id})
    session.execute(text("DELETE FROM customers WHERE merchant_id = :mid"), {"mid": merchant_id})
    session.execute(text("DELETE FROM merchants WHERE id = :mid"), {"mid": merchant_id})
    session.commit()
    session.close()
