import { useState } from 'react'
import type { CSSProperties } from 'react'
import { Card } from '../components/Card'
import { EmptyState, ErrorState, LoadingState, PageHeader } from '../components/PageState'
import { SimulationBadge } from '../components/StatusBadge'
import { useApiData } from '../hooks/useApiData'
import { api } from '../services/api'
import { formatDateTime, formatStageLabel } from '../utils/format'

const STAGES = [
  'EVENT_RECEIVED', 'CONTEXT_RETRIEVED', 'CAUSE_CLASSIFIED', 'RECOVERY_PREDICTED',
  'ACTION_PROPOSED', 'POLICY_CHECKED', 'ACTION_EXECUTED', 'OUTCOME_RECORDED', 'HUMAN_ESCALATED',
]

export function AuditLogsPage() {
  const [caseIdFilter, setCaseIdFilter] = useState('')
  const [stageFilter, setStageFilter] = useState('')
  const [page, setPage] = useState(0)
  const limit = 50

  const { data, loading, error, reload } = useApiData(
    () =>
      api.listAuditLogs({
        case_id: caseIdFilter.trim() || undefined,
        stage: stageFilter || undefined,
        limit,
        offset: page * limit,
      }),
    [caseIdFilter, stageFilter, page],
  )

  return (
    <div>
      <PageHeader title="Audit Logs" subtitle="Write-once, append-only trail of every pipeline decision." />

      <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
        <input
          value={caseIdFilter}
          onChange={(e) => {
            setCaseIdFilter(e.target.value)
            setPage(0)
          }}
          placeholder="Filter by case ID…"
          style={inputStyle}
        />
        <select
          value={stageFilter}
          onChange={(e) => {
            setStageFilter(e.target.value)
            setPage(0)
          }}
          style={selectStyle}
        >
          <option value="">All stages</option>
          {STAGES.map((s) => (
            <option key={s} value={s}>
              {formatStageLabel(s)}
            </option>
          ))}
        </select>
      </div>

      {loading && <LoadingState />}
      {error && <ErrorState message={error} onRetry={reload} />}

      {data && data.items.length === 0 && <EmptyState title="No audit entries match these filters" />}

      {data && data.items.length > 0 && (
        <>
          <Card style={{ padding: 0, overflow: 'hidden' }}>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5 }}>
                <thead>
                  <tr style={{ background: '#FAFBFC', borderBottom: '1px solid var(--color-border)' }}>
                    {['Timestamp', 'Case', 'Stage', 'Actor', 'Decision', 'Reason', 'Source'].map((h) => (
                      <th key={h} style={thStyle}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((entry) => (
                    <tr key={entry.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                      <td style={{ ...tdStyle, ...tdMono, whiteSpace: 'nowrap', color: 'var(--color-ink-muted)' }}>
                        {formatDateTime(entry.timestamp)}
                      </td>
                      <td style={{ ...tdStyle, ...tdMono }}>
                        {entry.recovery_case_id ? entry.recovery_case_id.slice(0, 8) : '—'}
                      </td>
                      <td style={tdStyle}>{formatStageLabel(entry.stage)}</td>
                      <td style={{ ...tdStyle, ...tdMono, fontSize: 11.5 }}>{entry.actor}</td>
                      <td style={{ ...tdStyle, ...tdMono, fontWeight: 600 }}>{entry.decision ?? '—'}</td>
                      <td style={{ ...tdStyle, maxWidth: 320, whiteSpace: 'normal', color: 'var(--color-ink-muted)' }}>
                        {entry.reason ?? '—'}
                      </td>
                      <td style={tdStyle}>
                        <SimulationBadge simulated={entry.simulation_status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 12 }}>
            <span style={{ fontSize: 12.5, color: 'var(--color-ink-muted)' }}>
              Showing {page * limit + 1}–{Math.min((page + 1) * limit, data.total)} of {data.total}
            </span>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0} style={pagerButtonStyle}>
                Previous
              </button>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={(page + 1) * limit >= data.total}
                style={pagerButtonStyle}
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

const inputStyle: CSSProperties = {
  flex: 1,
  maxWidth: 320,
  padding: '7px 12px',
  borderRadius: 6,
  border: '1px solid var(--color-border-strong)',
  fontSize: 13,
  fontFamily: 'var(--font-mono)',
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
  padding: '9px 12px',
  fontSize: 10.5,
  fontWeight: 600,
  color: 'var(--color-ink-muted)',
  textTransform: 'uppercase',
  letterSpacing: '0.03em',
}

const tdStyle: CSSProperties = {
  padding: '9px 12px',
  verticalAlign: 'top',
}

const tdMono: CSSProperties = {
  fontFamily: 'var(--font-mono)',
}

const pagerButtonStyle: CSSProperties = {
  padding: '6px 14px',
  borderRadius: 6,
  border: '1px solid var(--color-border-strong)',
  background: 'var(--color-surface)',
  fontSize: 12.5,
  cursor: 'pointer',
}
