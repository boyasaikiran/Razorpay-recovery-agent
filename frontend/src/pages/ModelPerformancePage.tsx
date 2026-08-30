import type { ReactNode } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { Badge } from '../components/StatusBadge'
import { Card, KpiCard } from '../components/Card'
import { ErrorState, LoadingState, PageHeader } from '../components/PageState'
import { useApiData } from '../hooks/useApiData'
import { api } from '../services/api'
import { formatPercent, formatCauseLabel } from '../utils/format'

export function ModelPerformancePage() {
  const { data, loading, error, reload } = useApiData(() => api.getModelsPerformance())

  return (
    <div>
      <PageHeader
        title="Model Performance"
        subtitle="Real metrics from the last training run — nothing on this page is estimated or fabricated."
      />

      {loading && <LoadingState />}
      {error && <ErrorState message={error} onRetry={reload} />}

      {data && (
        <>
          <SectionTitle>Cause Classifier (XGBoost, Diagnosis Path B)</SectionTitle>
          {!data.cause_classifier.available ? (
            <Card>
              <NotAvailable what="Cause classifier" command="python -m app.ml.train_cause_classifier" />
            </Card>
          ) : (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 16 }}>
                <KpiCard label="Validation Accuracy" value={formatPercent(data.cause_classifier.val_accuracy)} />
                <KpiCard label="Validation F1 (macro)" value={formatPercent(data.cause_classifier.val_f1_macro)} />
                <KpiCard label="Training Rows" value={String(data.cause_classifier.n_train)} />
                <KpiCard label="Validation Rows" value={String(data.cause_classifier.n_val)} />
              </div>
              <Card style={{ marginBottom: 32 }}>
                <div style={{ fontSize: 12.5, fontWeight: 600, marginBottom: 10 }}>
                  Cause Taxonomy ({data.cause_classifier.classes?.length} classes)
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {data.cause_classifier.classes?.map((c) => (
                    <Badge key={c} tone="info">
                      {formatCauseLabel(c)}
                    </Badge>
                  ))}
                </div>
                <p style={{ fontSize: 12, color: 'var(--color-ink-muted)', marginTop: 12, marginBottom: 0 }}>
                  Note: a per-class confusion matrix was not persisted at training time — only aggregate
                  accuracy/F1 are available here. LLM (Path C) fallback rate is not applicable in this
                  environment: 0 LLM calls were made since LLM_API_KEY is not configured.
                </p>
              </Card>
            </>
          )}

          <SectionTitle>Recovery Probability Model (XGBoost, Phase 7)</SectionTitle>
          {!data.recovery_probability.available ? (
            <Card>
              <NotAvailable
                what="Recovery probability model"
                command="python -m app.ml.train_recovery_probability"
              />
            </Card>
          ) : (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 16 }}>
                <KpiCard label="Precision" value={formatPercent(data.recovery_probability.val_precision)} />
                <KpiCard label="Recall" value={formatPercent(data.recovery_probability.val_recall)} />
                <KpiCard label="F1 Score" value={formatPercent(data.recovery_probability.val_f1)} />
                <KpiCard label="ROC-AUC" value={data.recovery_probability.val_roc_auc?.toFixed(3) ?? '—'} />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                {data.recovery_probability.calibration_curve && (
                  <Card>
                    <div style={{ fontSize: 12.5, fontWeight: 600, marginBottom: 10 }}>
                      Calibration Curve (Reliability)
                    </div>
                    <ResponsiveContainer width="100%" height={240}>
                      <LineChart
                        data={data.recovery_probability.calibration_curve.prob_pred.map((pred, i) => ({
                          predicted: pred,
                          actual: data.recovery_probability.calibration_curve!.prob_true[i],
                        }))}
                        margin={{ left: 0, right: 16 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                        <XAxis
                          dataKey="predicted"
                          type="number"
                          domain={[0, 1]}
                          tickFormatter={(v) => v.toFixed(1)}
                          tick={{ fontSize: 10 }}
                          label={{ value: 'Predicted probability', position: 'bottom', fontSize: 10, offset: -2 }}
                        />
                        <YAxis domain={[0, 1]} tickFormatter={(v) => v.toFixed(1)} tick={{ fontSize: 10 }} />
                        <Tooltip formatter={(v: number) => v.toFixed(3)} />
                        <Line
                          type="monotone"
                          dataKey="actual"
                          stroke="#12805C"
                          strokeWidth={2}
                          dot={{ r: 3 }}
                          name="Actual"
                        />
                      </LineChart>
                    </ResponsiveContainer>
                    <p style={{ fontSize: 11.5, color: 'var(--color-ink-muted)', marginTop: 4, marginBottom: 0 }}>
                      A perfectly calibrated model tracks the diagonal (predicted ≈ actual).
                    </p>
                  </Card>
                )}

                {data.recovery_probability.feature_importance && (
                  <Card>
                    <div style={{ fontSize: 12.5, fontWeight: 600, marginBottom: 10 }}>Feature Importance</div>
                    <ResponsiveContainer width="100%" height={240}>
                      <BarChart
                        layout="vertical"
                        data={Object.entries(data.recovery_probability.feature_importance)
                          .sort((a, b) => b[1] - a[1])
                          .map(([feature, importance]) => ({ feature, importance }))}
                        margin={{ left: 24, right: 16 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                        <XAxis type="number" tick={{ fontSize: 10 }} />
                        <YAxis dataKey="feature" type="category" width={130} tick={{ fontSize: 10 }} />
                        <Tooltip formatter={(v: number) => v.toFixed(4)} />
                        <Bar dataKey="importance" fill="#3B4C82" radius={[0, 3, 3, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </Card>
                )}
              </div>
            </>
          )}
        </>
      )}
    </div>
  )
}

function SectionTitle({ children }: { children: ReactNode }) {
  return <h2 style={{ fontSize: 15, fontWeight: 700, margin: '0 0 14px' }}>{children}</h2>
}

function NotAvailable({ what, command }: { what: string; command: string }) {
  return (
    <div style={{ fontSize: 13, color: 'var(--color-ink-muted)' }}>
      {what} artifacts not found. Train it first: <code className="mono">{command}</code>
    </div>
  )
}
