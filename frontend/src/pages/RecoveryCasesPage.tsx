import { useMemo, useState } from 'react'
import type { CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { Card } from '../components/Card'
import { EmptyState, ErrorState, LoadingState, PageHeader } from '../components/PageState'
import { OutcomeBadge, PolicyDecisionBadge, SimulationBadge } from '../components/StatusBadge'
import { useApiData } from '../hooks/useApiData'
import { api } from '../services/api'
import { formatCauseLabel, formatActionLabel, formatCurrency, formatDateTime, formatPercent } from '../utils/format'
import type { RecoveryCaseDetail } from '../types/api'

const STATUS_OPTIONS = ['open', 'diagnosed', 'decided', 'executed', 'closed']

export function RecoveryCasesPage() {
  const [statusFilter, setStatusFilter] = useState('')
  const [causeFilter, setCauseFilter] = useState('')

  const { data, loading, error, reload } = useApiData(
    () => api.listRecoveryCases({ status: statusFilter || undefined, limit: 200 }),
    [statusFilter],
  )

  const filteredItems = useMemo(() => {
    if (!data) return []
    if (!causeFilter) return data.items
    return data.items.filter((item) => item.diagnosis?.cause === causeFilter)
  }, [data, causeFilter])

  const availableCauses = useMemo(() => {
    if (!data) return []
    const set = new Set(data.items.map((i) => i.diagnosis?.cause).filter(Boolean) as string[])
    return Array.from(set).sort()
  }, [data])

  return (
    <div>
      <PageHeader
        title="Recovery Cases"
        subtitle="Every ingested payment/checkout/invoice failure and its pipeline outcome."
      />

      <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} style={selectStyle}>
          <option value="">All statuses</option>
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select value={causeFilter} onChange={(e) => setCauseFilter(e.target.value)} style={selectStyle}>
          <option value="">All causes</option>
          {availableCauses.map((c) => (
            <option key={c} value={c}>
              {formatCauseLabel(c)}
            </option>
          ))}
        </select>
      </div>

      {loading && <LoadingState />}
      {error && <ErrorState message={error} onRetry={reload} />}

      {data && filteredItems.length === 0 && (
        <EmptyState
          title="No recovery cases match these filters"
          hint="Try clearing filters, or ingest events via POST /api/v1/simulate/events."
        />
      )}

      {data && filteredItems.length > 0 && (
        <Card style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ background: '#FAFBFC', borderBottom: '1px solid var(--color-border)' }}>
                  {[
                    'Case ID', 'Event Type', 'Amount', 'Cause', 'Confidence',
                    'Recovery Prob.', 'Action', 'Policy', 'Outcome', '₹ Recovered', 'Status', 'Timestamp',
                  ].map((h) => (
                    <th key={h} style={thStyle}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredItems.map((c) => (
                  <CaseRow key={c.id} c={c} />
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}

function CaseRow({ c }: { c: RecoveryCaseDetail }) {
  return (
    <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
      <td style={tdStyle}>
        <Link
          to={`/trace?case=${c.id}`}
          className="mono"
          style={{ color: 'var(--color-primary)', fontSize: 12, textDecoration: 'none' }}
        >
          {c.id.slice(0, 8)}
        </Link>
      </td>
      <td style={tdStyle}>{c.case_type.replace(/_/g, ' ')}</td>
      <td style={{ ...tdStyle, ...tdMono }}>{formatCurrency(c.amount_at_risk, c.currency ?? 'INR')}</td>
      <td style={tdStyle}>{c.diagnosis ? formatCauseLabel(c.diagnosis.cause) : '—'}</td>
      <td style={{ ...tdStyle, ...tdMono }}>{c.diagnosis ? formatPercent(c.diagnosis.confidence) : '—'}</td>
      <td style={{ ...tdStyle, ...tdMono }}>
        {c.prediction ? formatPercent(c.prediction.recovery_probability) : '—'}
      </td>
      <td style={tdStyle}>{c.decision ? formatActionLabel(c.decision.proposed_action) : '—'}</td>
      <td style={tdStyle}>{c.decision ? <PolicyDecisionBadge decision={c.decision.policy_decision} /> : '—'}</td>
      <td style={tdStyle}>{c.outcome ? <OutcomeBadge status={c.outcome.status} /> : '—'}</td>
      <td style={{ ...tdStyle, ...tdMono }}>
        {c.outcome?.recovered_amount ? formatCurrency(c.outcome.recovered_amount, c.currency ?? 'INR') : '—'}
      </td>
      <td style={tdStyle}>
        {c.action ? (
          <SimulationBadge simulated={c.action.simulated} />
        ) : (
          <span style={{ color: 'var(--color-ink-muted)' }}>{c.status}</span>
        )}
      </td>
      <td style={{ ...tdStyle, ...tdMono, fontSize: 11.5, color: 'var(--color-ink-muted)' }}>
        {formatDateTime(c.created_at)}
      </td>
    </tr>
  )
}

const selectStyle: CSSProperties = {
  padding: '7px 12px',
  borderRadius: 6,
  border: '1px solid var(--color-border-strong)',
  background: 'var(--color-surface)',
  fontSize: 13,
  fontFamily: 'var(--font-ui)',
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
  fontVariantNumeric: 'tabular-nums',
}
