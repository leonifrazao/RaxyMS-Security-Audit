export interface KpiStats {
  totalAccounts: number
  activeFarms: number
  pointsToday: number
  pointsThisMonth: number
  successRate: number
  alerts?: number
}

export interface KpiDescriptor {
  id: keyof KpiStats
  label: string
  helper?: string
  formatter?: (value: number) => string
}
