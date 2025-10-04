import { apiFetch, getApiBaseUrl } from '@/lib/api-client'

import { type Account, type AccountStatus } from '../types'

const FALLBACK_ACCOUNTS: Account[] = [
  {
    id: 'acc-1',
    email: 'carla.souza@example.com',
    alias: 'Carla - BR',
    status: 'running',
    tier: 'Level 2',
    pointsBalance: 32870,
    dailyEarnings: 450,
    lastActivity: new Date(Date.now() - 1000 * 60 * 12).toISOString(),
    country: 'BR',
  },
  {
    id: 'acc-2',
    email: 'rodrigo.oliveira@example.com',
    status: 'idle',
    tier: 'Level 1',
    pointsBalance: 12450,
    dailyEarnings: 120,
    lastActivity: new Date(Date.now() - 1000 * 60 * 60 * 5).toISOString(),
    country: 'PT',
  },
  {
    id: 'acc-3',
    email: 'ana.ferreira@example.com',
    status: 'error',
    tier: 'Level 2',
    pointsBalance: 9820,
    dailyEarnings: 0,
    lastActivity: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
    errorMessage: 'Falha de autenticação',
    country: 'BR',
  },
]

export async function fetchAccounts(): Promise<Account[]> {
  const baseUrl = getApiBaseUrl()

  if (!baseUrl) {
    return FALLBACK_ACCOUNTS
  }

  try {
    const response = await apiFetch<AccountResponse[]>('/accounts')
    return response.map(normalizeAccount)
  } catch (error) {
    console.warn('[Dashboard] Falha ao obter contas, exibindo dados simulados.', error)
    return FALLBACK_ACCOUNTS
  }
}

interface AccountResponse extends Partial<Account> {
  id: string
  email: string
  status?: AccountStatus
  last_activity?: string
  points_balance?: number
  daily_earnings?: number
}

function normalizeAccount(account: AccountResponse): Account {
  return {
    id: account.id,
    email: account.email,
    alias: account.alias,
    status: account.status ?? 'idle',
    tier: account.tier ?? 'Level 1',
    pointsBalance: account.pointsBalance ?? account.points_balance ?? 0,
    dailyEarnings: account.dailyEarnings ?? account.daily_earnings ?? 0,
    lastActivity: account.lastActivity ?? account.last_activity ?? new Date().toISOString(),
    errorMessage: account.errorMessage,
    country: account.country,
  }
}
