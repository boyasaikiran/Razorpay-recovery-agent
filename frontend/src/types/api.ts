export type Cause =
  | 'insufficient_funds'
  | 'expired_payment_method'
  | 'temporary_bank_failure'
  | 'auth_otp_failure'
  | 'checkout_abandonment'
  | 'price_shock_abandonment'
  | 'bank_downtime'
  | 'overdue_invoice'
  | 'risk_block'
  | 'repeated_failure'
  | 'unknown'

export type RecoveryActionType =
  | 'RETRY_PAYMENT'
  | 'DELAYED_RETRY'
  | 'CREATE_PAYMENT_LINK'
  | 'SEND_NOTIFICATION'
  | 'LOG_PROMISE_TO_PAY'
  | 'ESCALATE_TO_HUMAN'
  | 'STOP_RECOVERY'

export type PolicyDecisionType = 'APPROVED' | 'DENIED' | 'ROUTE_TO_HUMAN'

export type OutcomeStatusType = 'success' | 'failure' | 'human_review' | 'stopped' | 'policy_denied'

export interface DiagnosisSummary {
  cause: Cause
  confidence: number
  method: 'rule_based' | 'xgboost' | 'llm' | 'llm_fallback'
  reason: string | null
}

export interface ModelPredictionSummary {
  recovery_probability: number
  model_name: string
  model_version: string
}

export interface DecisionSummary {
  proposed_action: RecoveryActionType
  policy_decision: PolicyDecisionType
  policy_reason: string | null
  policy_rule_triggered: string | null
}

export interface ActionSummary {
  action_type: RecoveryActionType
  status: string
  simulated: boolean
}

export interface OutcomeSummary {
  status: OutcomeStatusType
  recovered_amount: number | null
  currency: string | null
}

export interface RecoveryCaseSummary {
  id: string
  merchant_id: string
  customer_id: string | null
  case_type: string
  amount_at_risk: number | null
  currency: string | null
  status: string
  created_at: string
  updated_at: string
}

export interface RecoveryCaseDetail extends RecoveryCaseSummary {
  diagnosis: DiagnosisSummary | null
  prediction: ModelPredictionSummary | null
  decision: DecisionSummary | null
  action: ActionSummary | null
  outcome: OutcomeSummary | null
}

export interface RecoveryCaseListResponse {
  items: RecoveryCaseDetail[]
  total: number
  limit: number
  offset: number
}

export interface AuditLogEntry {
  id: string
  recovery_case_id: string | null
  timestamp: string
  stage: string
  actor: string
  decision: string | null
  reason: string | null
  input_reference: string | null
  output_reference: string | null
  simulation_status: boolean
}

export interface AuditLogListResponse {
  items: AuditLogEntry[]
  total: number
  limit: number
  offset: number
}

export interface RecoveryCaseTraceResponse {
  case_id: string
  entries: AuditLogEntry[]
}

export interface RunCaseResponse {
  case_id: string
  diagnosis: DiagnosisSummary
  prediction: ModelPredictionSummary
  proposed_action: RecoveryActionType
  policy_decision: PolicyDecisionType
  executed: boolean
  outcome: OutcomeSummary | null
}

export interface EvaluationReport {
  n_records_evaluated: number
  total_revenue_at_risk: number
  baseline_revenue_recovered: number
  orchestrator_revenue_recovered: number
  baseline_recovery_rate: number
  orchestrator_recovery_rate: number
  incremental_recovery: number
  incremental_recovery_pct_of_at_risk: number
  model_precision: number | null
  model_recall: number | null
  model_f1: number | null
  model_roc_auc: number | null
  cause_classification_accuracy: number
  automation_rate: number
  escalation_rate: number
  policy_violation_rate: number
  unauthorized_action_rate: number
  tool_success_rate: number
  avg_pipeline_latency_seconds: number
  llm_calls_made: number
  llm_malformed_output_rate: number | null
  notes: string[]
}

export interface CauseCount {
  cause: string
  count: number
}

export interface CauseRecovery {
  cause: string
  at_risk_amount: number
  recovered_amount: number
}

export interface PaymentMethodRecovery {
  payment_method: string
  recovered_amount: number
}

export interface MetricsResponse {
  revenue_at_risk: number
  revenue_recovered: number
  recovery_rate: number
  automation_rate: number
  escalation_rate: number
  policy_violations: number
  failed_recoveries: number
  active_cases: number
  total_cases: number
  cause_distribution: CauseCount[]
  recovery_by_cause: CauseRecovery[]
  recovery_by_payment_method: PaymentMethodRecovery[]
}

export interface PolicyResponse {
  cause: Cause
  allowed_actions: RecoveryActionType[]
  blocked_actions: RecoveryActionType[]
  confidence_threshold: number
  max_retries: number
  cooldown_seconds: number
  requires_consent: boolean
  blocks_on_risk_flag: boolean
  max_amount: number | null
}

export interface PolicyListResponse {
  items: PolicyResponse[]
}

export interface CauseClassifierPerformance {
  available: boolean
  model_version: string | null
  classes: string[] | null
  val_accuracy: number | null
  val_f1_macro: number | null
  n_train: number | null
  n_val: number | null
}

export interface CalibrationCurve {
  prob_true: number[]
  prob_pred: number[]
}

export interface RecoveryProbabilityPerformance {
  available: boolean
  model_version: string | null
  val_precision: number | null
  val_recall: number | null
  val_f1: number | null
  val_roc_auc: number | null
  calibration_curve: CalibrationCurve | null
  feature_importance: Record<string, number> | null
  n_train: number | null
  n_val: number | null
}

export interface ModelsPerformanceResponse {
  cause_classifier: CauseClassifierPerformance
  recovery_probability: RecoveryProbabilityPerformance
}

export interface HealthResponse {
  status: string
  service: string
  version: string
}
