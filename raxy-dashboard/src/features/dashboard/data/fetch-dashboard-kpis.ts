import { apiFetch, getApiBaseUrl } from '@/lib/api-client'

import { type KpiStats } from '../types'

const FALLBACK_KPIS: KpiStats = {
  totalAccounts: 42,
  activeFarms: 18,
  pointsToday: 3680,
  pointsThisMonth: 48720,
  successRate: 92.5,
  alerts: 3,
}

export async function fetchDashboardKpis(): Promise<KpiStats> {
  const baseUrl = getApiBaseUrl()

  if (!baseUrl) {
    return FALLBACK_KPIS
  }

  try {
    const response = await apiFetch<KpiResponse>('/dashboard/kpis')
    return normalizeKpis(response)
  } catch (error) {
    console.warn('[Dashboard] Falha ao obter KPIs, exibindo dados simulados.', error)
    return FALLBACK_KPIS
  }
}

interface KpiResponse extends Partial<KpiStats> {
  total_accounts?: number
  active_farms?: number
  points_today?: number
  points_month?: number
  success_rate?: number
  alerts?: number
}

function normalizeKpis(data: KpiResponse): KpiStats {
  return {
    totalAccounts: data.totalAccounts ?? data.total_accounts ?? FALLBACK_KPIS.totalAccounts,
    activeFarms: data.activeFarms ?? data.active_farms ?? FALLBACK_KPIS.activeFarms,
    pointsToday: data.pointsToday ?? data.points_today ?? FALLBACK_KPIS.pointsToday,
    pointsThisMonth: data.pointsThisMonth ?? data.points_month ?? FALLBACK_KPIS.pointsThisMonth,
    successRate: data.successRate ?? data.success_rate ?? FALLBACK_KPIS.successRate,
    alerts: data.alerts ?? FALLBACK_KPIS.alerts,
  }
}
