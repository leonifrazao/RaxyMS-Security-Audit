'use client'

import { useMemo } from 'react'
import { TrendingUp, TrendingDown, Activity, Target, Award, Zap } from 'lucide-react'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

import { type Account } from '@/features/accounts/types'

interface StatsOverviewProps {
  accounts: Account[]
}

export function StatsOverview({ accounts }: StatsOverviewProps) {
  const stats = useMemo(() => {
    const total = accounts.length
    const active = accounts.filter((a) => a.status === 'running').length
    const completed = accounts.filter((a) => a.status === 'completed').length
    const errors = accounts.filter((a) => a.status === 'error').length
    const idle = accounts.filter((a) => a.status === 'idle').length

    const totalPoints = accounts.reduce((sum, a) => sum + a.pointsBalance, 0)
    const totalDaily = accounts.reduce((sum, a) => sum + a.dailyEarnings, 0)
    const avgPoints = total > 0 ? totalPoints / total : 0

    const tierDistribution = {
      'Level 1': accounts.filter((a) => a.tier === 'Level 1').length,
      'Level 2': accounts.filter((a) => a.tier === 'Level 2').length,
      'Level 3': accounts.filter((a) => a.tier === 'Level 3').length,
    }

    const successRate = total > 0 ? ((completed / (completed + errors || 1)) * 100) : 100

    return {
      total,
      active,
      completed,
      errors,
      idle,
      totalPoints,
      totalDaily,
      avgPoints,
      tierDistribution,
      successRate,
    }
  }, [accounts])

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      <Card className="border-blue-500/20 bg-gradient-to-br from-blue-500/5 to-transparent">
        <CardHeader className="pb-2">
          <CardDescription className="flex items-center gap-2 text-xs font-medium">
            <Activity className="h-4 w-4 text-blue-500" />
            Status de Execução
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-bold text-blue-500">{stats.active}</span>
            <span className="text-sm text-muted-foreground">ativos agora</span>
          </div>
          <div className="space-y-2">
            <div className="flex justify-between text-xs">
              <span className="text-muted-foreground">Concluídos</span>
              <span className="font-medium text-emerald-500">{stats.completed}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-muted-foreground">Com erro</span>
              <span className="font-medium text-red-500">{stats.errors}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-muted-foreground">Aguardando</span>
              <span className="font-medium">{stats.idle}</span>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="border-emerald-500/20 bg-gradient-to-br from-emerald-500/5 to-transparent">
        <CardHeader className="pb-2">
          <CardDescription className="flex items-center gap-2 text-xs font-medium">
            <Award className="h-4 w-4 text-emerald-500" />
            Pontuação Total
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-bold text-emerald-500">
              {stats.totalPoints.toLocaleString('pt-BR')}
            </span>
            <span className="text-sm text-muted-foreground">pts</span>
          </div>
          <div className="space-y-2">
            <div className="flex justify-between text-xs">
              <span className="text-muted-foreground">Média por conta</span>
              <span className="font-medium">{Math.round(stats.avgPoints)} pts</span>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <TrendingUp className="h-3 w-3 text-emerald-500" />
              <span className="text-muted-foreground">Hoje</span>
              <span className="font-medium text-emerald-500">
                +{stats.totalDaily.toLocaleString('pt-BR')}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="border-purple-500/20 bg-gradient-to-br from-purple-500/5 to-transparent">
        <CardHeader className="pb-2">
          <CardDescription className="flex items-center gap-2 text-xs font-medium">
            <Target className="h-4 w-4 text-purple-500" />
            Taxa de Sucesso
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-bold text-purple-500">
              {stats.successRate.toFixed(1)}%
            </span>
          </div>
          <Progress value={stats.successRate} className="h-2" />
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            {stats.successRate >= 90 ? (
              <>
                <TrendingUp className="h-3 w-3 text-emerald-500" />
                <span>Excelente desempenho</span>
              </>
            ) : stats.successRate >= 70 ? (
              <>
                <Activity className="h-3 w-3 text-yellow-500" />
                <span>Bom desempenho</span>
              </>
            ) : (
              <>
                <TrendingDown className="h-3 w-3 text-red-500" />
                <span>Requer atenção</span>
              </>
            )}
          </div>
        </CardContent>
      </Card>

      <Card className="border-amber-500/20 bg-gradient-to-br from-amber-500/5 to-transparent">
        <CardHeader className="pb-2">
          <CardDescription className="flex items-center gap-2 text-xs font-medium">
            <Zap className="h-4 w-4 text-amber-500" />
            Distribuição de Tiers
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-bold text-amber-500">{stats.total}</span>
            <span className="text-sm text-muted-foreground">contas</span>
          </div>
          <div className="space-y-2">
            {Object.entries(stats.tierDistribution).map(([tier, count]) => (
              <div key={tier} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <Badge
                    variant="outline"
                    className={cn(
                      'h-5 px-1.5 text-[10px]',
                      tier === 'Level 1' && 'border-bronze-500/50 text-bronze-500',
                      tier === 'Level 2' && 'border-silver-500/50 text-silver-500',
                      tier === 'Level 3' && 'border-amber-500/50 text-amber-500'
                    )}
                  >
                    {tier}
                  </Badge>
                </div>
                <span className="font-medium">{count}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
