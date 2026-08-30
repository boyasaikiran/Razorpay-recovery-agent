import type { CSSProperties } from 'react'
import { Badge } from '../components/StatusBadge'
import { Card } from '../components/Card'
import { ErrorState, LoadingState, PageHeader } from '../components/PageState'
import { useApiData } from '../hooks/useApiData'
import { api } from '../services/api'
import { formatActionLabel, formatCauseLabel, formatCurrency, formatPercent } from '../utils/format'
import type { PolicyResponse } from '../types/api'

export function PoliciesPage() {
  const { data, loading, error, reload } = useApiData(() => api.listPolicies())

  return (
    <div>
      <PageHeader
        title="Policies"
        subtitle="The deterministic policy engine's real configuration — this, not the LLM, has final say on every action."
      />

      {loading && <LoadingState />}
      {error && <ErrorState message={error} onRetry={reload} />}

      {data && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {data.items.map((p) => (
            <PolicyCard key={p.cause} policy={p} />
          ))}
        </div>
      )}
    </div>
  )
}

function PolicyCard({ policy }: { policy: PolicyResponse }) {
  return (
    <Card>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 14 }}>
        <div style={{ fontSize: 15, fontWeight: 700 }}>{formatCauseLabel(policy.cause)}</div>
        <div style={{ display: 'flex', gap: 16, fontSize: 12 }}>
          <Field label="Confidence threshold" value={formatPercent(policy.confidence_threshold)} />
          <Field label="Max retries" value={String(policy.max_retries)} />
          <Field label="Cooldown" value={`${policy.cooldown_seconds}s`} />
          <Field
            label="Max amount"
            value={policy.max_amount != null ? formatCurrency(policy.max_amount) : 'No cap'}
          />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        <div>
          <div style={sectionLabelStyle}>Allowed Actions</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {policy.allowed_actions.map((a) => (
              <Badge key={a} tone="success">
                {formatActionLabel(a)}
              </Badge>
            ))}
          </div>
        </div>
        <div>
          <div style={sectionLabelStyle}>Blocked Actions</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {policy.blocked_actions.length === 0 ? (
              <span style={{ fontSize: 12, color: 'var(--color-ink-muted)' }}>None explicitly blocked</span>
            ) : (
              policy.blocked_actions.map((a) => (
                <Badge key={a} tone="danger">
                  {formatActionLabel(a)}
                </Badge>
              ))
            )}
          </div>
        </div>
      </div>

      <div
        style={{ display: 'flex', gap: 20, marginTop: 14, paddingTop: 14, borderTop: '1px solid var(--color-border)' }}
      >
        <RequirementChip label="Requires consent" active={policy.requires_consent} />
        <RequirementChip label="Blocks on risk flag" active={policy.blocks_on_risk_flag} />
      </div>
    </Card>
  )
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div
        style={{ color: 'var(--color-ink-muted)', fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '0.02em' }}
      >
        {label}
      </div>
      <div className="mono" style={{ fontWeight: 600, fontSize: 13 }}>
        {value}
      </div>
    </div>
  )
}

function RequirementChip({ label, active }: { label: string; active: boolean }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12.5 }}>
      <span
        style={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          background: active ? 'var(--color-success)' : 'var(--color-border-strong)',
        }}
      />
      {label}
    </div>
  )
}

const sectionLabelStyle: CSSProperties = {
  fontSize: 10.5,
  fontWeight: 600,
  color: 'var(--color-ink-muted)',
  textTransform: 'uppercase',
  letterSpacing: '0.03em',
  marginBottom: 8,
}
