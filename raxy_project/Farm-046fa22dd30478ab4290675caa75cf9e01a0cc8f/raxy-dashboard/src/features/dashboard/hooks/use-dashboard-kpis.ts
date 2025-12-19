'use client'

import { useQuery } from '@tanstack/react-query'

import { fetchDashboardKpis } from '../data/fetch-dashboard-kpis'
import { type KpiStats } from '../types'

const KPI_QUERY_KEY = ['dashboard', 'kpis'] as const

export function useDashboardKpis(initialData?: KpiStats) {
  return useQuery({
    queryKey: KPI_QUERY_KEY,
    queryFn: fetchDashboardKpis,
    initialData,
    staleTime: 1000 * 60,
    refetchInterval: 1000 * 60,
  })
}
