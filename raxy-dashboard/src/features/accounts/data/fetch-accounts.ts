import { apiFetch, getApiBaseUrl } from '@/lib/api-client'

import { type Account, type AccountSource } from '../types'

const DEFAULT_TIER: Account['tier'] = 'Level 1'
const DEFAULT_STATUS: Account['status'] = 'idle'

export async function fetchAccounts(source: AccountSource = 'file'): Promise<Account[]> {
  const endpoint = source === 'database' ? '/api/v1/accounts/database' : '/api/v1/accounts'
  const response = await apiFetch<AccountsResponse>(endpoint)
  return response.accounts.map((account) => normalizeAccount(account, source))
}

interface AccountApiResponse {
  email: string
  profile_id?: string
  password?: string | null
  proxy?: string | null
  source?: AccountSource
  last_activity?: string | null
  points_balance?: number | null
  daily_earnings?: number | null
  alias?: string | null
  country?: string | null
}

interface AccountsResponse {
  accounts: AccountApiResponse[]
}

function normalizeAccount(account: AccountApiResponse, fallbackSource: AccountSource): Account {
  const profileId = account.profile_id ?? buildProfileId(account.email)
  const source = account.source ?? fallbackSource
  return {
    id: `${source}-${profileId}`,
    email: account.email,
    profileId,
    status: DEFAULT_STATUS,
    tier: DEFAULT_TIER,
    pointsBalance: account.points_balance ?? 0,
    dailyEarnings: account.daily_earnings ?? 0,
    lastActivity: account.last_activity ?? new Date().toISOString(),
    proxy: account.proxy ?? null,
    password: account.password ?? null,
    alias: account.alias ?? undefined,
    errorMessage: undefined,
    country: account.country ?? undefined,
    source,
  }
}

export function buildProfileId(email: string) {
  return email.replace(/@/g, '_at_').replace(/[^a-zA-Z0-9._-]/g, '_')
}
