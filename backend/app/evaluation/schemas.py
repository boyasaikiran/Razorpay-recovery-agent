from typing import Optional

from pydantic import BaseModel


class EvaluationReport(BaseModel):
    n_records_evaluated: int

    total_revenue_at_risk: float
    baseline_revenue_recovered: float
    orchestrator_revenue_recovered: float
    baseline_recovery_rate: float
    orchestrator_recovery_rate: float
    incremental_recovery: float
    incremental_recovery_pct_of_at_risk: float

    model_precision: Optional[float]
    model_recall: Optional[float]
    model_f1: Optional[float]
    model_roc_auc: Optional[float]

    cause_classification_accuracy: float

    automation_rate: float
    escalation_rate: float
    policy_violation_rate: float
    unauthorized_action_rate: float
    tool_success_rate: float
    avg_pipeline_latency_seconds: float

    llm_calls_made: int
    llm_malformed_output_rate: Optional[float]

    notes: list[str]
