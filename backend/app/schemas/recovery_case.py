import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.audit_log import AuditLogEntry


class RecoveryCaseSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    merchant_id: uuid.UUID
    customer_id: Optional[uuid.UUID]
    case_type: str
    amount_at_risk: Optional[float]
    currency: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime


class DiagnosisSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    cause: str
    confidence: float
    method: str
    reason: Optional[str]


class ModelPredictionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    recovery_probability: float
    model_name: str
    model_version: str


class DecisionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    proposed_action: str
    policy_decision: str
    policy_reason: Optional[str]
    policy_rule_triggered: Optional[str]


class ActionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    action_type: str
    status: str
    simulated: bool


class OutcomeSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: str
    recovered_amount: Optional[float]
    currency: Optional[str]


class RecoveryCaseDetail(RecoveryCaseSummary):
    diagnosis: Optional[DiagnosisSummary] = None
    prediction: Optional[ModelPredictionSummary] = None
    decision: Optional[DecisionSummary] = None
    action: Optional[ActionSummary] = None
    outcome: Optional[OutcomeSummary] = None


class RecoveryCaseListResponse(BaseModel):
    items: list[RecoveryCaseDetail]
    total: int
    limit: int
    offset: int


class RecoveryCaseTraceResponse(BaseModel):
    case_id: uuid.UUID
    entries: list[AuditLogEntry]


class RunCaseResponse(BaseModel):
    case_id: uuid.UUID
    diagnosis: DiagnosisSummary
    prediction: ModelPredictionSummary
    proposed_action: str
    policy_decision: str
    executed: bool
    outcome: Optional[OutcomeSummary] = None
