export type AccountStatus = 'idle' | 'running' | 'error' | 'paused' | 'completed'

export type AccountSource = 'file' | 'database' | 'manual'

export interface Account {
  id: string
  email: string
  profileId: string
  status: AccountStatus
  tier: 'Level 1' | 'Level 2' | 'Level 3'
  pointsBalance: number
  dailyEarnings: number
  lastActivity: string
  proxy?: string | null
  password?: string | null
  alias?: string
  errorMessage?: string | null
  country?: string
  source: AccountSource
}

export interface CreateAccountPayload {
  email: string
  password: string
  proxy?: string
}
