import type { CSSProperties, ReactNode } from 'react'

export function Card({ children, style }: { children: ReactNode; style?: CSSProperties }) {
  return (
    <div
      style={{
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-md)',
        boxShadow: 'var(--shadow-card)',
        padding: 20,
        ...style,
      }}
    >
      {children}
    </div>
  )
}

export function KpiCard({
  label,
  value,
  sublabel,
  accent,
}: {
  label: string
  value: string
  sublabel?: string
  accent?: 'success' | 'danger' | 'warning' | 'default'
}) {
  const accentColor =
    accent === 'success'
      ? 'var(--color-success)'
      : accent === 'danger'
        ? 'var(--color-danger)'
        : accent === 'warning'
          ? 'var(--color-warning)'
          : 'var(--color-ink)'

  return (
    <Card>
      <div
        style={{
          fontSize: 12,
          fontWeight: 600,
          color: 'var(--color-ink-muted)',
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
          marginBottom: 8,
        }}
      >
        {label}
      </div>
      <div className="mono" style={{ fontSize: 28, fontWeight: 600, color: accentColor, lineHeight: 1.1 }}>
        {value}
      </div>
      {sublabel && <div style={{ fontSize: 12, color: 'var(--color-ink-muted)', marginTop: 6 }}>{sublabel}</div>}
    </Card>
  )
}
