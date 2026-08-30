"""
Import all models here so that Base.metadata sees every table.
Required for Alembic autogenerate to work correctly.
"""
from app.models.merchant import Merchant  # noqa: F401
from app.models.customer import Customer  # noqa: F401
from app.models.payment_event import PaymentEvent  # noqa: F401
from app.models.subscription import Subscription  # noqa: F401
from app.models.invoice import Invoice  # noqa: F401
from app.models.recovery_case import RecoveryCase  # noqa: F401
from app.models.diagnosis import Diagnosis  # noqa: F401
from app.models.model_prediction import ModelPrediction  # noqa: F401
from app.models.decision import Decision  # noqa: F401
from app.models.action import Action  # noqa: F401
from app.models.outcome import Outcome  # noqa: F401
from app.models.policy import Policy  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
