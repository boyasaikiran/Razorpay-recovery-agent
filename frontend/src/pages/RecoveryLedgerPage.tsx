import { useMemo } from 'react'
import type { CSSProperties } from 'react'
import { Card, KpiCard } from '../components/Card'
import { EmptyState, ErrorState, LoadingState, PageHeader } from '../components/PageState'
import { OutcomeBadge, SimulationBadge } from '../components/StatusBadge'
import { useApiData } from '../hooks/useApiData'
import { api } from '../services/api'
import { formatActionLabel, formatCauseLabel, formatCurrency, formatDateTime } from '../utils/format'

export function RecoveryLedgerPage() {
  const { data, loading, error, reload } = useApiData(() => api.listRecoveryCases({ limit: 500 }))

  const ledgerRows = useMemo(() => {
    if (!data) return []
    return data.items
      .filter((c) => c.outcome !== null)
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
  }, [data])

  const totalRecovered = useMemo(
    () => ledgerRows.reduce((sum, c) => sum + (c.outcome?.recovered_amount ?? 0), 0),
    [ledgerRows],
  )
  const successCount = ledgerRows.filter((c) => c.outcome?.status === 'success').length

  return (
    <div>
      <PageHeader
        title="Recovery Ledger"
        subtitle="Every case that reached a terminal outcome, with the amount recovered."
      />

      {loading && <LoadingState />}
      {error && <ErrorState message={error} onRetry={reload} />}

      {data && ledgerRows.length === 0 && (
        <EmptyState
          title="No completed recoveries yet"
          hint="Run a case from Recovery Cases or Agent Trace to populate the ledger."
        />
      )}

      {data && ledgerRows.length > 0 && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 20 }}>
            <KpiCard label="Total Recovered" value={formatCurrency(totalRecovered)} accent="success" />
            <KpiCard label="Successful Recoveries" value={`${successCount} / ${ledgerRows.length}`} />
            <KpiCard
              label="Avg. Recovered per Success"
              value={successCount > 0 ? formatCurrency(totalRecovered / successCount) : '—'}
            />
          </div>

          <Card style={{ padding: 0, overflow: 'hidden' }}>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr style={{ background: '#FAFBFC', borderBottom: '1px solid var(--color-border)' }}>
                    {['Case ID', 'Cause', 'Action Taken', 'Outcome', 'Amount Recovered', 'Source', 'Recorded'].map(
                      (h) => (
                        <th key={h} style={thStyle}>
                          {h}
                        </th>
                      ),
                    )}
                  </tr>
                </thead>
                <tbody>
                  {ledgerRows.map((c) => (
                    <tr key={c.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                      <td style={{ ...tdStyle, ...tdMono }}>{c.id.slice(0, 8)}</td>
                      <td style={tdStyle}>{c.diagnosis ? formatCauseLabel(c.diagnosis.cause) : '—'}</td>
                      <td style={tdStyle}>{c.decision ? formatActionLabel(c.decision.proposed_action) : '—'}</td>
                      <td style={tdStyle}>
                        <OutcomeBadge status={c.outcome!.status} />
                      </td>
                      <td
                        style={{
                          ...tdStyle,
                          ...tdMono,
                          fontWeight: 600,
                          color: c.outcome!.status === 'success' ? 'var(--color-success)' : 'var(--color-ink-muted)',
                        }}
                      >
                        {c.outcome?.recovered_amount
                          ? formatCurrency(c.outcome.recovered_amount, c.currency ?? 'INR')
                          : '—'}
                      </td>
                      <td style={tdStyle}>{c.action && <SimulationBadge simulated={c.action.simulated} />}</td>
                      <td style={{ ...tdStyle, ...tdMono, fontSize: 11.5, color: 'var(--color-ink-muted)' }}>
                        {formatDateTime(c.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  )
}

const thStyle: CSSProperties = {
  textAlign: 'left',
  padding: '10px 14px',
  fontSize: 11,
  fontWeight: 600,
  color: 'var(--color-ink-muted)',
  textTransform: 'uppercase',
  letterSpacing: '0.03em',
  whiteSpace: 'nowrap',
}

const tdStyle: CSSProperties = {
  padding: '10px 14px',
  whiteSpace: 'nowrap',
}

const tdMono: CSSProperties = {
  fontFamily: 'var(--font-mono)',
}
