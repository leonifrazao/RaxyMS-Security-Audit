import { getApiBaseUrl } from '@/lib/api-client'

import { fetchAccounts } from '@/features/accounts/data/fetch-accounts'

import { type KpiStats } from '../types'

export async function fetchDashboardKpis(): Promise<KpiStats> {
  const baseUrl = getApiBaseUrl()

  if (!baseUrl) {
    throw new Error('NEXT_PUBLIC_RAXY_API_URL não configurada para o dashboard.')
  }

  try {
    const [fileAccounts, databaseAccounts] = await Promise.all([
      fetchAccounts('file'),
      fetchAccounts('database'),
    ])

    const totalAccounts = fileAccounts.length + databaseAccounts.length
    const pointsToday = sumPoints(fileAccounts) + sumPoints(databaseAccounts)

    return {
      totalAccounts,
      activeFarms: 0,
      pointsToday,
      pointsThisMonth: pointsToday,
      successRate: totalAccounts > 0 ? 100 : 0,
      alerts: 0,
    }
  } catch (error) {
    console.warn('[Dashboard] Falha ao calcular KPIs.', error)
    throw error
  }
}

function sumPoints(accounts: Array<{ pointsBalance: number }>) {
  return accounts.reduce((total, account) => total + (account.pointsBalance ?? 0), 0)
}
