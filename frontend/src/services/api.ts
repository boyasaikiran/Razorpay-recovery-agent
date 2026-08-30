import type {
  AuditLogListResponse,
  EvaluationReport,
  HealthResponse,
  MetricsResponse,
  ModelsPerformanceResponse,
  PolicyListResponse,
  RecoveryCaseDetail,
  RecoveryCaseListResponse,
  RecoveryCaseTraceResponse,
  RunCaseResponse,
} from '../types/api'

const BASE = '/api/v1'

// NOTE (Phase 15 security tradeoff, documented explicitly): this key is
// bundled into client-side JS via Vite's import.meta.env, which means
// it is NOT truly secret once served to a browser -- anyone can read it
// from the built bundle. This is an accepted tradeoff for an internal
// ops dashboard behind a private network, matching this MVP's scope.
// A public-facing production deployment would need session-based auth
// (login + short-lived token/cookie) instead of a static shared key.
const API_KEY = import.meta.env.VITE_API_KEY as string | undefined

class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(API_KEY ? { 'X-API-Key': API_KEY } : {}),
    },
    ...init,
  })
  if (!res.ok) {
    let message = `Request failed (${res.status})`
    try {
      const body = await res.json()
      message = body?.error?.message ?? message
    } catch {
      // response wasn't JSON
    }
    throw new ApiError(message, res.status)
  }
  return res.json() as Promise<T>
}

function qs(params: Record<string, string | number | boolean | undefined>): string {
  const usable = Object.entries(params).filter(([, v]) => v !== undefined && v !== '')
  if (usable.length === 0) return ''
  return '?' + usable.map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`).join('&')
}

export const api = {
  health: () => request<HealthResponse>('/health'),

  getMetrics: () => request<MetricsResponse>('/metrics'),

  listPolicies: () => request<PolicyListResponse>('/policies'),

  getModelsPerformance: () => request<ModelsPerformanceResponse>('/models/performance'),

  listRecoveryCases: (params: { status?: string; case_type?: string; limit?: number; offset?: number } = {}) =>
    request<RecoveryCaseListResponse>(`/recovery-cases${qs(params)}`),

  getRecoveryCase: (caseId: string) => request<RecoveryCaseDetail>(`/recovery-cases/${caseId}`),

  getRecoveryCaseTrace: (caseId: string) =>
    request<RecoveryCaseTraceResponse>(`/recovery-cases/${caseId}/trace`),

  runRecoveryCase: (caseId: string) =>
    request<RunCaseResponse>(`/recovery-cases/${caseId}/run`, { method: 'POST' }),

  listAuditLogs: (
    params: {
      case_id?: string
      stage?: string
      actor?: string
      simulation_status?: boolean
      limit?: number
      offset?: number
    } = {},
  ) => request<AuditLogListResponse>(`/audit-logs${qs(params)}`),

  runEvaluation: (n_records: number = 100) =>
    request<EvaluationReport>(`/evaluation/run${qs({ n_records })}`, { method: 'POST' }),
}

export { ApiError }
