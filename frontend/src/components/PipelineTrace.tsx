import type { CSSProperties } from 'react'
import { Badge } from './StatusBadge'
import { formatDateTime, formatStageLabel } from '../utils/format'
import type { AuditLogEntry } from '../types/api'

const STAGE_TONE: Record<string, { dot: string; label: string }> = {
  EVENT_RECEIVED: { dot: '#6B7690', label: 'Event' },
  CONTEXT_RETRIEVED: { dot: '#6B7690', label: 'Context' },
  CAUSE_CLASSIFIED: { dot: '#3B4C82', label: 'Diagnosis' },
  RECOVERY_PREDICTED: { dot: '#3B6FA8', label: 'Recovery Probability' },
  ACTION_PROPOSED: { dot: '#8A5FBF', label: 'Action Proposed' },
  POLICY_CHECKED: { dot: '#12805C', label: 'Policy Check' },
  ACTION_EXECUTED: { dot: '#12805C', label: 'Execution' },
  OUTCOME_RECORDED: { dot: '#B5790A', label: 'Outcome' },
  HUMAN_ESCALATED: { dot: '#B5790A', label: 'Human Escalation' },
}

function toneForEntry(entry: AuditLogEntry): { dot: string; ring: string } {
  const decision = entry.decision ?? ''
  if (decision === 'DENIED' || decision.includes('failure') || decision === 'execution_refused') {
    return { dot: '#B23B3B', ring: 'rgba(178,59,59,0.15)' }
  }
  if (decision === 'ROUTE_TO_HUMAN' || decision === 'route_to_human' || decision.includes('human_review')) {
    return { dot: '#B5790A', ring: 'rgba(181,121,10,0.15)' }
  }
  if (decision === 'APPROVED' || decision.includes('success') || decision === 'ingested') {
    return { dot: '#12805C', ring: 'rgba(18,128,92,0.15)' }
  }
  const base = STAGE_TONE[entry.stage]?.dot ?? '#6B7690'
  return { dot: base, ring: `${base}22` }
}

export function PipelineTrace({ entries }: { entries: AuditLogEntry[] }) {
  return (
    <div style={{ position: 'relative', paddingLeft: 4 }}>
      {entries.map((entry, i) => {
        const isLast = i === entries.length - 1
        const tone = toneForEntry(entry)
        const stageMeta = STAGE_TONE[entry.stage]

        return (
          <div key={entry.id} style={{ display: 'flex', gap: 16 }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: 20 }}>
              <div
                style={{
                  width: 14,
                  height: 14,
                  borderRadius: '50%',
                  background: tone.dot,
                  boxShadow: `0 0 0 5px ${tone.ring}`,
                  flexShrink: 0,
                  marginTop: 4,
                }}
              />
              {!isLast && (
                <div style={{ width: 2, flex: 1, background: 'var(--color-border-strong)', minHeight: 36 }} />
              )}
            </div>

            <div style={{ flex: 1, paddingBottom: isLast ? 0 : 20 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <span style={{ fontSize: 13.5, fontWeight: 700 }}>
                  {stageMeta?.label ?? formatStageLabel(entry.stage)}
                </span>
                <Badge tone="neutral">{entry.stage}</Badge>
                {entry.simulation_status && <Badge tone="neutral">SIMULATED</Badge>}
                <span className="mono" style={{ fontSize: 11, color: 'var(--color-ink-muted)', marginLeft: 'auto' }}>
                  {formatDateTime(entry.timestamp)}
                </span>
              </div>

              {entry.decision && (
                <div className="mono" style={{ fontSize: 12.5, fontWeight: 600, color: tone.dot, marginBottom: 2 }}>
                  {entry.decision}
                </div>
              )}

              {entry.reason && (
                <div style={{ fontSize: 12.5, color: 'var(--color-ink-muted)', lineHeight: 1.5 }}>{entry.reason}</div>
              )}

              <div style={{ fontSize: 11, color: 'var(--color-ink-muted)', marginTop: 4 }}>
                actor: <span className="mono">{entry.actor}</span>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

export const pipelineCardStyle: CSSProperties = {
  padding: '24px 28px',
}
