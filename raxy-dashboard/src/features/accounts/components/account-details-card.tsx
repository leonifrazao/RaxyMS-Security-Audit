'use client'

import { Mail, Shield, Globe, Calendar, TrendingUp, Award } from 'lucide-react'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Progress } from '@/components/ui/progress'
import { cn } from '@/lib/utils'

import { type Account } from '../types'

interface AccountDetailsCardProps {
  account: Account
}

export function AccountDetailsCard({ account }: AccountDetailsCardProps) {
  const progressToNextLevel = calculateProgressToNextLevel(account.pointsBalance, account.tier)

  return (
    <Card className="overflow-hidden">
      <div
        className={cn(
          'h-2 w-full',
          account.tier === 'Level 1' && 'bg-gradient-to-r from-orange-500 to-orange-600',
          account.tier === 'Level 2' && 'bg-gradient-to-r from-slate-400 to-slate-500',
          account.tier === 'Level 3' && 'bg-gradient-to-r from-amber-500 to-amber-600'
        )}
      />
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <CardTitle className="flex items-center gap-2">
              <Mail className="h-5 w-5 text-muted-foreground" />
              {account.email}
            </CardTitle>
            {account.alias && (
              <CardDescription className="flex items-center gap-2">
                <Shield className="h-4 w-4" />
                {account.alias}
              </CardDescription>
            )}
          </div>
          <Badge
            variant="outline"
            className={cn(
              'text-sm font-semibold',
              account.tier === 'Level 1' && 'border-orange-500 bg-orange-500/10 text-orange-600',
              account.tier === 'Level 2' && 'border-slate-500 bg-slate-500/10 text-slate-600',
              account.tier === 'Level 3' && 'border-amber-500 bg-amber-500/10 text-amber-600'
            )}
          >
            <Award className="mr-1 h-3 w-3" />
            {account.tier}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-6">
        <div className="grid gap-4 sm:grid-cols-3">
          <StatItem
            icon={TrendingUp}
            label="Saldo Total"
            value={account.pointsBalance.toLocaleString('pt-BR')}
            suffix="pontos"
            valueClassName="text-2xl font-bold text-emerald-600 dark:text-emerald-400"
          />
          <StatItem
            icon={Calendar}
            label="Hoje"
            value={`+${account.dailyEarnings.toLocaleString('pt-BR')}`}
            suffix="pontos"
            valueClassName="text-2xl font-bold text-blue-600 dark:text-blue-400"
          />
          <StatItem
            icon={Globe}
            label="Origem"
            value={account.source}
            valueClassName="text-lg font-semibold capitalize"
          />
        </div>

        <Separator />

        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Progresso para próximo tier</span>
            <span className="font-medium">{progressToNextLevel}%</span>
          </div>
          <Progress value={progressToNextLevel} className="h-3" />
          <p className="text-xs text-muted-foreground">
            Continue acumulando pontos para desbloquear benefícios exclusivos
          </p>
        </div>

        <Separator />

        <div className="grid gap-3 text-sm">
          <InfoRow label="Profile ID" value={account.profileId} />
          <InfoRow label="Status" value={account.status} badge />
          {account.proxy && <InfoRow label="Proxy" value={account.proxy} />}
          {account.country && <InfoRow label="País" value={account.country} />}
          <InfoRow
            label="Última atividade"
            value={new Date(account.lastActivity).toLocaleString('pt-BR')}
          />
        </div>

        {account.errorMessage && (
          <>
            <Separator />
            <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-3">
              <p className="text-sm font-medium text-red-600 dark:text-red-400">
                Erro recente:
              </p>
              <p className="text-xs text-red-600/80 dark:text-red-400/80">
                {account.errorMessage}
              </p>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}

function StatItem({
  icon: Icon,
  label,
  value,
  suffix,
  valueClassName,
}: {
  icon: React.ElementType
  label: string
  value: string
  suffix?: string
  valueClassName?: string
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Icon className="h-4 w-4" />
        {label}
      </div>
      <div>
        <p className={cn('font-semibold', valueClassName)}>{value}</p>
        {suffix && <p className="text-xs text-muted-foreground">{suffix}</p>}
      </div>
    </div>
  )
}

function InfoRow({
  label,
  value,
  badge,
}: {
  label: string
  value: string
  badge?: boolean
}) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted-foreground">{label}</span>
      {badge ? (
        <Badge variant="outline" className="capitalize">
          {value}
        </Badge>
      ) : (
        <span className="font-medium">{value}</span>
      )}
    </div>
  )
}

function calculateProgressToNextLevel(points: number, currentTier: string): number {
  const tiers = {
    'Level 1': { min: 0, max: 10000 },
    'Level 2': { min: 10000, max: 50000 },
    'Level 3': { min: 50000, max: 100000 },
  }

  const tier = tiers[currentTier as keyof typeof tiers]
  if (!tier) return 0

  if (points >= tier.max) return 100

  const range = tier.max - tier.min
  const progress = points - tier.min
  return Math.min(100, Math.max(0, (progress / range) * 100))
}
