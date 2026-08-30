import type { ReactNode } from 'react'

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        marginBottom: 28,
        gap: 16,
      }}
    >
      <div>
        <h1 style={{ fontSize: 22, fontWeight: 700, margin: 0, letterSpacing: '-0.01em' }}>{title}</h1>
        {subtitle && <p style={{ fontSize: 13.5, color: 'var(--color-ink-muted)', margin: '6px 0 0' }}>{subtitle}</p>}
      </div>
      {actions && <div style={{ display: 'flex', gap: 8 }}>{actions}</div>}
    </div>
  )
}

export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return (
    <div style={{ padding: '48px 0', textAlign: 'center', color: 'var(--color-ink-muted)', fontSize: 13.5 }}>
      {label}
    </div>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div
      style={{
        padding: '20px 24px',
        borderRadius: 'var(--radius-md)',
        background: 'var(--color-danger-tint)',
        color: 'var(--color-danger)',
        fontSize: 13.5,
      }}
    >
      <strong>Couldn't load this page.</strong> {message}
      {onRetry && (
        <button
          onClick={onRetry}
          style={{
            marginLeft: 12,
            border: '1px solid var(--color-danger)',
            background: 'transparent',
            color: 'var(--color-danger)',
            borderRadius: 6,
            padding: '4px 10px',
            fontSize: 12.5,
            cursor: 'pointer',
          }}
        >
          Retry
        </button>
      )}
    </div>
  )
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div
      style={{
        padding: '48px 24px',
        textAlign: 'center',
        border: '1px dashed var(--color-border-strong)',
        borderRadius: 'var(--radius-md)',
        color: 'var(--color-ink-muted)',
      }}
    >
      <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-ink)', marginBottom: 4 }}>{title}</div>
      {hint && <div style={{ fontSize: 13 }}>{hint}</div>}
    </div>
  )
}
