import type { CSSProperties, ReactNode } from 'react'

export type BadgeTone = 'success' | 'warning' | 'danger' | 'info' | 'neutral'

const TONE_STYLES: Record<BadgeTone, CSSProperties> = {
  success: { background: 'var(--color-success-tint)', color: 'var(--color-success)' },
  warning: { background: 'var(--color-warning-tint)', color: 'var(--color-warning)' },
  danger: { background: 'var(--color-danger-tint)', color: 'var(--color-danger)' },
  info: { background: 'var(--color-info-tint)', color: 'var(--color-info)' },
  neutral: { background: '#EEF0F3', color: 'var(--color-ink-muted)' },
}

export function Badge({ tone, children }: { tone: BadgeTone; children: ReactNode }) {
  return (
    <span
      style={{
        ...TONE_STYLES[tone],
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        padding: '2px 8px',
        borderRadius: 999,
        fontSize: 11,
        fontWeight: 600,
        fontFamily: 'var(--font-mono)',
        letterSpacing: '0.02em',
        textTransform: 'uppercase',
        lineHeight: '18px',
        whiteSpace: 'nowrap',
      }}
    >
      {children}
    </span>
  )
}

/** REAL vs SIMULATED — must never mislead the viewer, per spec. */
export function SimulationBadge({ simulated }: { simulated: boolean }) {
  return simulated ? <Badge tone="neutral">SIMULATED</Badge> : <Badge tone="info">REAL</Badge>
}

export function PolicyDecisionBadge({ decision }: { decision: string }) {
  if (decision === 'APPROVED') return <Badge tone="success">APPROVED</Badge>
  if (decision === 'DENIED') return <Badge tone="danger">POLICY BLOCKED</Badge>
  if (decision === 'ROUTE_TO_HUMAN') return <Badge tone="warning">HUMAN REVIEW</Badge>
  return <Badge tone="neutral">{decision}</Badge>
}

export function OutcomeBadge({ status }: { status: string }) {
  switch (status) {
    case 'success':
      return <Badge tone="success">RECOVERED</Badge>
    case 'failure':
      return <Badge tone="danger">FAILED</Badge>
    case 'human_review':
      return <Badge tone="warning">HUMAN REVIEW</Badge>
    case 'stopped':
      return <Badge tone="neutral">STOPPED</Badge>
    case 'policy_denied':
      return <Badge tone="danger">POLICY BLOCKED</Badge>
    default:
      return <Badge tone="neutral">{status.toUpperCase()}</Badge>
  }
}
