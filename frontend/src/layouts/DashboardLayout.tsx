import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'

const NAV_ITEMS = [
  { to: '/', label: 'Overview', end: true },
  { to: '/cases', label: 'Recovery Cases' },
  { to: '/trace', label: 'Agent Trace' },
  { to: '/ledger', label: 'Recovery Ledger' },
  { to: '/metrics', label: 'Metrics' },
  { to: '/policies', label: 'Policies' },
  { to: '/audit-logs', label: 'Audit Logs' },
  { to: '/model-performance', label: 'Model Performance' },
]

export function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      <aside
        style={{
          width: 232,
          flexShrink: 0,
          background: 'var(--color-nav-bg)',
          color: 'var(--color-nav-text)',
          display: 'flex',
          flexDirection: 'column',
          position: 'sticky',
          top: 0,
          height: '100vh',
        }}
      >
        <div style={{ padding: '22px 20px 18px', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: '#fff', letterSpacing: '-0.01em' }}>
            Recovery Orchestrator
          </div>
          <div
            className="mono"
            style={{ fontSize: 10, color: '#8792A8', marginTop: 4, textTransform: 'uppercase', letterSpacing: '0.06em' }}
          >
            AI Revenue Recovery
          </div>
        </div>

        <nav style={{ flex: 1, padding: '12px 10px', display: 'flex', flexDirection: 'column', gap: 2 }}>
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              style={({ isActive }) => ({
                display: 'block',
                padding: '9px 12px',
                borderRadius: 6,
                fontSize: 13.5,
                fontWeight: isActive ? 600 : 500,
                color: isActive ? 'var(--color-nav-text-active)' : 'var(--color-nav-text)',
                background: isActive ? 'rgba(255,255,255,0.08)' : 'transparent',
                textDecoration: 'none',
                transition: 'background 120ms ease, color 120ms ease',
              })}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div
          style={{
            padding: '14px 20px',
            borderTop: '1px solid rgba(255,255,255,0.08)',
            fontSize: 11,
            color: '#6B7690',
          }}
        >
          <span className="mono">v0.1.0</span> · simulated demo data
        </div>
      </aside>

      <main style={{ flex: 1, minWidth: 0 }}>
        <div style={{ maxWidth: 1280, margin: '0 auto', padding: '32px 40px 64px' }}>{children}</div>
      </main>
    </div>
  )
}
