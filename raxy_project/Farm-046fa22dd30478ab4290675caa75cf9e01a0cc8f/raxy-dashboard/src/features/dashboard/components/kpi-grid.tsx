'use client'

import {
  type LucideIcon,
  AlertTriangle,
  Coins,
  PlayCircle,
  TrendingUp,
  Users,
} from 'lucide-react'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

import { useDashboardKpis } from '@/features/dashboard/hooks/use-dashboard-kpis'
import { type KpiStats } from '../types'

const KPI_CONFIG: Array<{
  id: keyof KpiStats
  label: string
  description: string
  icon: LucideIcon
  formatter?: (value: number) => string
  tone?: string
}> = [
  {
    id: 'totalAccounts',
    label: 'Contas cadastradas',
    description: 'Total de contas gerenciadas pelo farm',
    icon: Users,
  },
  {
    id: 'activeFarms',
    label: 'Farms ativos',
    description: 'Contas processando agora',
    icon: PlayCircle,
    tone: 'text-emerald-500 dark:text-emerald-400',
  },
  {
    id: 'pointsToday',
    label: 'Pontos hoje',
    description: 'Pontuação acumulada nas últimas 24h',
    icon: Coins,
    formatter: formatNumber,
  },
  {
    id: 'pointsThisMonth',
    label: 'Pontos no mês',
    description: 'Pontuação acumulada no período corrente',
    icon: TrendingUp,
    formatter: formatNumber,
  },
  {
    id: 'successRate',
    label: 'Taxa de sucesso',
    description: 'Execuções concluídas sem falhas',
    icon: TrendingUp,
    formatter: (value) => `${value.toFixed(1)}%`,
    tone: 'text-emerald-500 dark:text-emerald-400',
  },
  {
    id: 'alerts',
    label: 'Alertas críticos',
    description: 'Ações exigindo atenção manual',
    icon: AlertTriangle,
    formatter: (value) => value.toString(),
    tone: 'text-red-500 dark:text-red-400',
  },
]

function formatNumber(value: number) {
  return new Intl.NumberFormat('pt-BR').format(value)
}

export function KpiGrid({ kpiData }: { kpiData: KpiStats }) {
  const { data, isLoading, isFetching } = useDashboardKpis(kpiData)
  const metrics = data ?? kpiData
  const cards = KPI_CONFIG.filter((kpi) => typeof metrics[kpi.id] !== 'undefined')

  if (isLoading && !data) {
    return <KpiGridSkeleton />
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {cards.map((kpi) => (
        <KpiCard
          key={kpi.id}
          label={kpi.label}
          description={kpi.description}
          icon={kpi.icon}
          value={kpi.formatter ? kpi.formatter(metrics[kpi.id] ?? 0) : (metrics[kpi.id] ?? 0)}
          tone={kpi.tone}
          subtlePulse={isFetching}
        />
      ))}
    </div>
  )
}

interface KpiCardProps {
  label: string
  description: string
  icon: LucideIcon
  value: number | string
  tone?: string
  subtlePulse?: boolean
}

function KpiCard({ label, description, icon: Icon, value, tone, subtlePulse }: KpiCardProps) {
  return (
    <Card
      className={cn(
        'group relative overflow-hidden border-border/60 bg-gradient-to-br from-card to-card/50 backdrop-blur transition-all hover:shadow-lg hover:border-primary/50',
        subtlePulse ? 'animate-pulse' : ''
      )}
    >
      <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-transparent opacity-0 transition-opacity group-hover:opacity-100" />
      <CardHeader className="relative space-y-0 pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-medium text-muted-foreground">{label}</CardTitle>
          <div className={cn('rounded-full p-2 transition-colors group-hover:bg-primary/10', tone ? 'bg-muted' : '')}>
            <Icon className={cn('h-5 w-5 text-muted-foreground transition-colors group-hover:text-primary', tone)} aria-hidden />
          </div>
        </div>
        <CardDescription className="text-xs text-muted-foreground/80">{description}</CardDescription>
      </CardHeader>
      <CardContent className="relative">
        <span className={cn('text-3xl font-bold tracking-tight', tone)}>{value}</span>
      </CardContent>
    </Card>
  )
}

function KpiGridSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {Array.from({ length: 4 }).map((_, index) => (
        <Card key={index} className="border-border/60 bg-card/60">
          <CardHeader className="space-y-2 pb-2">
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-3 w-2/3" />
          </CardHeader>
          <CardContent>
            <Skeleton className="h-8 w-1/2" />
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
