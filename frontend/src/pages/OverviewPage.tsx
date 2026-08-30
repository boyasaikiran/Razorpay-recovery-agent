import { useState } from 'react'
import type { CSSProperties, ReactNode } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { Card, KpiCard } from '../components/Card'
import { EmptyState, ErrorState, LoadingState, PageHeader } from '../components/PageState'
import { useApiData } from '../hooks/useApiData'
import { api } from '../services/api'
import { formatCauseLabel, formatCurrency, formatPercent } from '../utils/format'
import type { EvaluationReport } from '../types/api'

const PIE_COLORS = [
  '#3B4C82', '#3B6FA8', '#12805C', '#B5790A', '#B23B3B',
  '#6B7690', '#8A5FBF', '#3E8E8E', '#A8763B', '#5C6BC0', '#7A8B99',
]

export function OverviewPage() {
  const metrics = useApiData(() => api.getMetrics())
  const [evalReport, setEvalReport] = useState<EvaluationReport | null>(null)
  const [evalLoading, setEvalLoading] = useState(false)
  const [evalError, setEvalError] = useState<string | null>(null)

  const runEvaluation = async () => {
    setEvalLoading(true)
    setEvalError(null)
    try {
      const report = await api.runEvaluation(150)
      setEvalReport(report)
    } catch (err) {
      setEvalError(err instanceof Error ? err.message : 'Evaluation failed')
    } finally {
      setEvalLoading(false)
    }
  }

  return (
    <div>
      <PageHeader
        title="Overview"
        subtitle="Live case metrics from the database, plus an on-demand baseline comparison."
      />

      {metrics.loading && <LoadingState label="Loading live metrics…" />}
      {metrics.error && <ErrorState message={metrics.error} onRetry={metrics.reload} />}

      {metrics.data && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 16 }}>
            <KpiCard label="Revenue at Risk" value={formatCurrency(metrics.data.revenue_at_risk)} />
            <KpiCard label="₹ Recovered" value={formatCurrency(metrics.data.revenue_recovered)} accent="success" />
            <KpiCard label="Recovery Rate" value={formatPercent(metrics.data.recovery_rate)} />
            <KpiCard
              label="Active Recovery Cases"
              value={String(metrics.data.active_cases)}
              sublabel={`${metrics.data.total_cases} total cases`}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 32 }}>
            <KpiCard label="Automation Rate" value={formatPercent(metrics.data.automation_rate)} />
            <KpiCard
              label="Human Escalation Rate"
              value={formatPercent(metrics.data.escalation_rate)}
              accent="warning"
            />
            <KpiCard
              label="Policy Violations"
              value={String(metrics.data.policy_violations)}
              accent={metrics.data.policy_violations > 0 ? 'danger' : 'success'}
              sublabel="Must always be zero"
            />
            <KpiCard label="Failed Recoveries" value={String(metrics.data.failed_recoveries)} accent="danger" />
          </div>

          {metrics.data.total_cases === 0 ? (
            <EmptyState
              title="No recovery cases yet"
              hint="Ingest events via POST /api/v1/simulate/events or run the evaluation below to see live data here."
            />
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 32 }}>
              <Card>
                <ChartTitle>Cause Distribution</ChartTitle>
                <ResponsiveContainer width="100%" height={260}>
                  <PieChart>
                    <Pie
                      data={metrics.data.cause_distribution}
                      dataKey="count"
                      nameKey="cause"
                      innerRadius={55}
                      outerRadius={90}
                      paddingAngle={2}
                    >
                      {metrics.data.cause_distribution.map((entry, i) => (
                        <Cell key={entry.cause} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(v: number, _n, p) => [v, formatCauseLabel(String(p.payload.cause))]} />
                    <Legend formatter={(value) => formatCauseLabel(String(value))} wrapperStyle={{ fontSize: 11 }} />
                  </PieChart>
                </ResponsiveContainer>
              </Card>

              <Card>
                <ChartTitle>Revenue at Risk vs Recovered, by Cause</ChartTitle>
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={metrics.data.recovery_by_cause} margin={{ left: 0, right: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                    <XAxis dataKey="cause" tickFormatter={(v) => formatCauseLabel(v).split(' ')[0]} tick={{ fontSize: 10 }} />
                    <YAxis tick={{ fontSize: 10 }} />
                    <Tooltip formatter={(v: number) => formatCurrency(v)} labelFormatter={(l) => formatCauseLabel(String(l))} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Bar dataKey="at_risk_amount" name="At Risk" fill="#C9CEDA" radius={[3, 3, 0, 0]} />
                    <Bar dataKey="recovered_amount" name="Recovered" fill="#12805C" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </Card>
            </div>
          )}
        </>
      )}

      <Card>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div>
            <ChartTitle>Baseline vs Orchestrator</ChartTitle>
            <p style={{ fontSize: 12.5, color: 'var(--color-ink-muted)', margin: '4px 0 0' }}>
              Runs the batch evaluation engine (150 fresh synthetic records) on demand — compares this
              system against a fixed-retry, no-cause-awareness baseline.
            </p>
          </div>
          <button onClick={runEvaluation} disabled={evalLoading} style={runButtonStyle}>
            {evalLoading ? 'Running…' : 'Run Evaluation'}
          </button>
        </div>

        {evalError && <ErrorState message={evalError} />}

        {evalReport && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginTop: 16 }}>
            <KpiCard label="Baseline Recovery Rate" value={formatPercent(evalReport.baseline_recovery_rate)} />
            <KpiCard
              label="Orchestrator Recovery Rate"
              value={formatPercent(evalReport.orchestrator_recovery_rate)}
              accent="success"
            />
            <KpiCard
              label="Incremental Recovery"
              value={formatCurrency(evalReport.incremental_recovery)}
              sublabel={`+${formatPercent(evalReport.incremental_recovery_pct_of_at_risk)} of at-risk revenue`}
              accent="success"
            />
          </div>
        )}
      </Card>
    </div>
  )
}

function ChartTitle({ children }: { children: ReactNode }) {
  return <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>{children}</div>
}

const runButtonStyle: CSSProperties = {
  background: 'var(--color-primary)',
  color: '#fff',
  border: 'none',
  borderRadius: 6,
  padding: '8px 16px',
  fontSize: 13,
  fontWeight: 600,
  cursor: 'pointer',
  whiteSpace: 'nowrap',
}
