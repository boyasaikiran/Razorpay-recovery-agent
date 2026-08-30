import { Route, Routes } from 'react-router-dom'
import { DashboardLayout } from './layouts/DashboardLayout'
import { AgentTracePage } from './pages/AgentTracePage'
import { AuditLogsPage } from './pages/AuditLogsPage'
import { MetricsPage } from './pages/MetricsPage'
import { ModelPerformancePage } from './pages/ModelPerformancePage'
import { OverviewPage } from './pages/OverviewPage'
import { PoliciesPage } from './pages/PoliciesPage'
import { RecoveryCasesPage } from './pages/RecoveryCasesPage'
import { RecoveryLedgerPage } from './pages/RecoveryLedgerPage'

function App() {
  return (
    <DashboardLayout>
      <Routes>
        <Route path="/" element={<OverviewPage />} />
        <Route path="/cases" element={<RecoveryCasesPage />} />
        <Route path="/trace" element={<AgentTracePage />} />
        <Route path="/ledger" element={<RecoveryLedgerPage />} />
        <Route path="/metrics" element={<MetricsPage />} />
        <Route path="/policies" element={<PoliciesPage />} />
        <Route path="/audit-logs" element={<AuditLogsPage />} />
        <Route path="/model-performance" element={<ModelPerformancePage />} />
      </Routes>
    </DashboardLayout>
  )
}

export default App
