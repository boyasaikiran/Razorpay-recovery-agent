import { useEffect, useState } from 'react'
import type { CSSProperties, ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Card } from '../components/Card'
import { EmptyState, ErrorState, LoadingState, PageHeader } from '../components/PageState'
import { PipelineTrace } from '../components/PipelineTrace'
import { OutcomeBadge, PolicyDecisionBadge } from '../components/StatusBadge'
import { useApiData } from '../hooks/useApiData'
import { api } from '../services/api'
import { formatCauseLabel, formatCurrency, formatPercent } from '../utils/format'

export function AgentTracePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const preselected = searchParams.get('case') ?? ''
  const [caseIdInput, setCaseIdInput] = useState(preselected)
  const [activeCaseId, setActiveCaseId] = useState(preselected)

  const recentCases = useApiData(() => api.listRecoveryCases({ limit: 25 }))
  const detail = useApiData(
    () => (activeCaseId ? api.getRecoveryCase(activeCaseId) : Promise.resolve(null)),
    [activeCaseId],
  )
  const trace = useApiData(
    () => (activeCaseId ? api.getRecoveryCaseTrace(activeCaseId) : Promise.resolve(null)),
    [activeCaseId],
  )

  useEffect(() => {
    if (preselected && preselected !== activeCaseId) {
      setActiveCaseId(preselected)
      setCaseIdInput(preselected)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preselected])

  const selectCase = (id: string) => {
    setActiveCaseId(id)
    setCaseIdInput(id)
    setSearchParams({ case: id })
  }

  return (
    <div>
      <PageHeader
        title="Agent Trace"
        subtitle="The full pipeline for a single case: event → diagnosis → policy → execution → outcome → audit."
      />

      <div style={{ display: 'flex', gap: 10, marginBottom: 20 }}>
        <input
          value={caseIdInput}
          onChange={(e) => setCaseIdInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && selectCase(caseIdInput.trim())}
          placeholder="Paste a case ID…"
          style={inputStyle}
        />
        <button onClick={() => selectCase(caseIdInput.trim())} style={buttonStyle} disabled={!caseIdInput.trim()}>
          View Trace
        </button>
      </div>

      {!activeCaseId && (
        <Card>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>Recent Cases</div>
          {recentCases.loading && <LoadingState />}
          {recentCases.data && recentCases.data.items.length === 0 && (
            <EmptyState title="No cases yet" hint="Ingest and run a case to see its trace here." />
          )}
          {recentCases.data && recentCases.data.items.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {recentCases.data.items.map((c) => (
                <button key={c.id} onClick={() => selectCase(c.id)} style={recentCaseRowStyle}>
                  <span className="mono" style={{ fontSize: 12, color: 'var(--color-primary)' }}>
                    {c.id.slice(0, 8)}
                  </span>
                  <span style={{ fontSize: 12.5, color: 'var(--color-ink-muted)' }}>
                    {c.diagnosis ? formatCauseLabel(c.diagnosis.cause) : c.case_type}
                  </span>
                  <span style={{ marginLeft: 'auto', fontSize: 12.5 }}>
                    {formatCurrency(c.amount_at_risk, c.currency ?? 'INR')}
                  </span>
                </button>
              ))}
            </div>
          )}
        </Card>
      )}

      {activeCaseId && (
        <>
          {detail.loading && <LoadingState label="Loading case…" />}
          {detail.error && <ErrorState message={detail.error} onRetry={detail.reload} />}

          {detail.data && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, marginBottom: 20 }}>
              <SummaryChip
                label="Amount"
                value={formatCurrency(detail.data.amount_at_risk, detail.data.currency ?? 'INR')}
              />
              <SummaryChip
                label="Cause"
                value={detail.data.diagnosis ? formatCauseLabel(detail.data.diagnosis.cause) : '—'}
              />
              <SummaryChip
                label="Recovery Prob."
                value={detail.data.prediction ? formatPercent(detail.data.prediction.recovery_probability) : '—'}
              />
              <SummaryChip
                label="Policy"
                value={
                  detail.data.decision ? <PolicyDecisionBadge decision={detail.data.decision.policy_decision} /> : '—'
                }
              />
              <SummaryChip
                label="Outcome"
                value={detail.data.outcome ? <OutcomeBadge status={detail.data.outcome.status} /> : '—'}
              />
            </div>
          )}

          <Card style={{ padding: '28px 32px' }}>
            {trace.loading && <LoadingState label="Loading trace…" />}
            {trace.error && <ErrorState message={trace.error} onRetry={trace.reload} />}
            {trace.data && trace.data.entries.length === 0 && <EmptyState title="No audit trail yet for this case" />}
            {trace.data && trace.data.entries.length > 0 && <PipelineTrace entries={trace.data.entries} />}
          </Card>
        </>
      )}
    </div>
  )
}

function SummaryChip({ label, value }: { label: string; value: ReactNode }) {
  return (
    <Card style={{ padding: '12px 16px' }}>
      <div
        style={{
          fontSize: 10.5,
          fontWeight: 600,
          color: 'var(--color-ink-muted)',
          textTransform: 'uppercase',
          letterSpacing: '0.03em',
          marginBottom: 4,
        }}
      >
        {label}
      </div>
      <div className="mono" style={{ fontSize: 14, fontWeight: 600 }}>
        {value}
      </div>
    </Card>
  )
}

const inputStyle: CSSProperties = {
  flex: 1,
  maxWidth: 400,
  padding: '8px 12px',
  borderRadius: 6,
  border: '1px solid var(--color-border-strong)',
  fontSize: 13,
  fontFamily: 'var(--font-mono)',
}

const buttonStyle: CSSProperties = {
  background: 'var(--color-primary)',
  color: '#fff',
  border: 'none',
  borderRadius: 6,
  padding: '8px 16px',
  fontSize: 13,
  fontWeight: 600,
  cursor: 'pointer',
}

const recentCaseRowStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 12,
  padding: '8px 10px',
  border: '1px solid var(--color-border)',
  borderRadius: 6,
  background: 'var(--color-surface)',
  cursor: 'pointer',
  textAlign: 'left',
  width: '100%',
}
