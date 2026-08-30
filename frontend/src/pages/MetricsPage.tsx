import type { ReactNode } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Card, KpiCard } from '../components/Card'
import { EmptyState, ErrorState, LoadingState, PageHeader } from '../components/PageState'
import { useApiData } from '../hooks/useApiData'
import { api } from '../services/api'
import { formatCauseLabel, formatCurrency, formatPercent } from '../utils/format'

export function MetricsPage() {
  const { data, loading, error, reload } = useApiData(() => api.getMetrics())

  return (
    <div>
      <PageHeader title="Metrics" subtitle="Full breakdown of live case data currently in the database." />

      {loading && <LoadingState />}
      {error && <ErrorState message={error} onRetry={reload} />}

      {data && data.total_cases === 0 && (
        <EmptyState title="No data yet" hint="Ingest and run cases to populate these metrics." />
      )}

      {data && data.total_cases > 0 && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 16 }}>
            <KpiCard label="Revenue at Risk" value={formatCurrency(data.revenue_at_risk)} />
            <KpiCard label="Revenue Recovered" value={formatCurrency(data.revenue_recovered)} accent="success" />
            <KpiCard label="Recovery Rate" value={formatPercent(data.recovery_rate)} />
            <KpiCard label="Total Cases" value={String(data.total_cases)} />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 32 }}>
            <KpiCard label="Automation Rate" value={formatPercent(data.automation_rate)} />
            <KpiCard label="Escalation Rate" value={formatPercent(data.escalation_rate)} accent="warning" />
            <KpiCard
              label="Policy Violations"
              value={String(data.policy_violations)}
              accent={data.policy_violations > 0 ? 'danger' : 'success'}
            />
            <KpiCard label="Failed Recoveries" value={String(data.failed_recoveries)} accent="danger" />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <Card>
              <ChartTitle>Recovery by Cause</ChartTitle>
              {data.recovery_by_cause.length === 0 ? (
                <EmptyState title="No cause data yet" />
              ) : (
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={data.recovery_by_cause} margin={{ left: 0, right: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                    <XAxis
                      dataKey="cause"
                      tickFormatter={(v) => formatCauseLabel(v).split(' ')[0]}
                      tick={{ fontSize: 10 }}
                    />
                    <YAxis tick={{ fontSize: 10 }} />
                    <Tooltip
                      formatter={(v: number) => formatCurrency(v)}
                      labelFormatter={(l) => formatCauseLabel(String(l))}
                    />
                    <Bar dataKey="recovered_amount" fill="#12805C" radius={[3, 3, 0, 0]} name="Recovered" />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </Card>

            <Card>
              <ChartTitle>Recovery by Payment Method</ChartTitle>
              {data.recovery_by_payment_method.length === 0 ? (
                <EmptyState title="No payment method data yet" />
              ) : (
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={data.recovery_by_payment_method} margin={{ left: 0, right: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                    <XAxis dataKey="payment_method" tick={{ fontSize: 10 }} />
                    <YAxis tick={{ fontSize: 10 }} />
                    <Tooltip formatter={(v: number) => formatCurrency(v)} />
                    <Bar dataKey="recovered_amount" fill="#3B6FA8" radius={[3, 3, 0, 0]} name="Recovered" />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  )
}

function ChartTitle({ children }: { children: ReactNode }) {
  return <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>{children}</div>
}
