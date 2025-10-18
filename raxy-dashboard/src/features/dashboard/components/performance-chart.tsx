'use client'

import { useMemo } from 'react'
import { TrendingUp, BarChart3 } from 'lucide-react'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'

import { type Account } from '@/features/accounts/types'

interface PerformanceChartProps {
  accounts: Account[]
}

export function PerformanceChart({ accounts }: PerformanceChartProps) {
  const chartData = useMemo(() => {
    // Agrupar contas por faixas de pontos
    const ranges = [
      { label: '0-5k', min: 0, max: 5000, count: 0, color: 'bg-red-500' },
      { label: '5k-10k', min: 5000, max: 10000, count: 0, color: 'bg-orange-500' },
      { label: '10k-20k', min: 10000, max: 20000, count: 0, color: 'bg-yellow-500' },
      { label: '20k-50k', min: 20000, max: 50000, count: 0, color: 'bg-emerald-500' },
      { label: '50k+', min: 50000, max: Infinity, count: 0, color: 'bg-blue-500' },
    ]

    accounts.forEach((account) => {
      const range = ranges.find((r) => account.pointsBalance >= r.min && account.pointsBalance < r.max)
      if (range) range.count++
    })

    const maxCount = Math.max(...ranges.map((r) => r.count), 1)
    
    return ranges.map((range) => ({
      ...range,
      percentage: (range.count / maxCount) * 100,
    }))
  }, [accounts])

  const topPerformers = useMemo(() => {
    return [...accounts]
      .sort((a, b) => b.pointsBalance - a.pointsBalance)
      .slice(0, 5)
  }, [accounts])

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5" />
            Distribuição de Pontos
          </CardTitle>
          <CardDescription>Contas agrupadas por faixa de pontuação</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {chartData.map((range) => (
              <div key={range.label} className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium">{range.label}</span>
                  <span className="text-muted-foreground">{range.count} contas</span>
                </div>
                <div className="relative h-8 overflow-hidden rounded-full bg-muted">
                  <div
                    className={cn('h-full transition-all duration-500', range.color)}
                    style={{ width: `${range.percentage}%` }}
                  />
                  <div className="absolute inset-0 flex items-center justify-center text-xs font-medium text-white mix-blend-difference">
                    {range.count > 0 && `${Math.round((range.count / accounts.length) * 100)}%`}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5" />
            Top 5 Contas
          </CardTitle>
          <CardDescription>Maiores pontuações acumuladas</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {topPerformers.map((account, index) => (
              <div
                key={account.id}
                className="flex items-center gap-4 rounded-lg border p-3 transition-colors hover:bg-muted/50"
              >
                <div
                  className={cn(
                    'flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full font-bold',
                    index === 0 && 'bg-amber-500/20 text-amber-500',
                    index === 1 && 'bg-slate-400/20 text-slate-400',
                    index === 2 && 'bg-orange-600/20 text-orange-600',
                    index > 2 && 'bg-muted text-muted-foreground'
                  )}
                >
                  {index + 1}
                </div>
                <div className="flex-1 space-y-1">
                  <p className="text-sm font-medium">{account.email}</p>
                  <p className="text-xs text-muted-foreground">{account.tier}</p>
                </div>
                <div className="text-right">
                  <p className="text-lg font-bold text-emerald-600 dark:text-emerald-400">
                    {account.pointsBalance.toLocaleString('pt-BR')}
                  </p>
                  <p className="text-xs text-muted-foreground">pontos</p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
