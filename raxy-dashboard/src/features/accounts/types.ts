export type AccountStatus = 'idle' | 'running' | 'error' | 'paused' | 'completed'

export interface Account {
  id: string
  email: string
  alias?: string
  status: AccountStatus
  tier: 'Level 1' | 'Level 2' | 'Level 3'
  pointsBalance: number
  dailyEarnings: number
  lastActivity: string
  errorMessage?: string | null
  country?: string
}

export interface CreateAccountPayload {
  email: string
  password: string
  proxy?: string
}
