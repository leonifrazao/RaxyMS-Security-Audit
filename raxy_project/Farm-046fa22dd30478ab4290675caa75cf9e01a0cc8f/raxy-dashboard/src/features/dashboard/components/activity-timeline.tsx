'use client'

import { Clock, CheckCircle2, XCircle, AlertCircle, PlayCircle } from 'lucide-react'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

import { type Account } from '@/features/accounts/types'

interface ActivityTimelineProps {
  accounts: Account[]
}

export function ActivityTimeline({ accounts }: ActivityTimelineProps) {
  const recentActivities = accounts
    .map((account) => ({
      id: account.id,
      email: account.email,
      status: account.status,
      lastActivity: account.lastActivity,
      pointsBalance: account.pointsBalance,
      dailyEarnings: account.dailyEarnings,
      errorMessage: account.errorMessage,
    }))
    .sort((a, b) => new Date(b.lastActivity).getTime() - new Date(a.lastActivity).getTime())
    .slice(0, 10)

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Clock className="h-5 w-5" />
              Atividades Recentes
            </CardTitle>
            <CardDescription>Últimas 10 atividades registradas</CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[400px] pr-4">
          <div className="space-y-4">
            {recentActivities.map((activity, index) => (
              <div
                key={activity.id}
                className={cn(
                  'flex gap-4 rounded-lg border p-3 transition-colors hover:bg-muted/50',
                  index === 0 && 'border-primary/50 bg-primary/5'
                )}
              >
                <div className="flex-shrink-0 pt-1">
                  {activity.status === 'completed' && (
                    <CheckCircle2 className="h-5 w-5 text-emerald-500" />
                  )}
                  {activity.status === 'running' && (
                    <PlayCircle className="h-5 w-5 animate-pulse text-blue-500" />
                  )}
                  {activity.status === 'error' && (
                    <XCircle className="h-5 w-5 text-red-500" />
                  )}
                  {activity.status === 'idle' && (
                    <Clock className="h-5 w-5 text-muted-foreground" />
                  )}
                  {activity.status === 'paused' && (
                    <AlertCircle className="h-5 w-5 text-yellow-500" />
                  )}
                </div>

                <div className="flex-1 space-y-1">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium">{activity.email}</p>
                    <Badge
                      variant="outline"
                      className={cn(
                        'text-xs',
                        activity.status === 'completed' && 'border-emerald-500/50 text-emerald-500',
                        activity.status === 'running' && 'border-blue-500/50 text-blue-500',
                        activity.status === 'error' && 'border-red-500/50 text-red-500',
                        activity.status === 'idle' && 'border-muted-foreground/50',
                        activity.status === 'paused' && 'border-yellow-500/50 text-yellow-500'
                      )}
                    >
                      {activity.status}
                    </Badge>
                  </div>

                  <div className="flex items-center gap-4 text-xs text-muted-foreground">
                    <span>
                      {new Date(activity.lastActivity).toLocaleString('pt-BR', {
                        day: '2-digit',
                        month: 'short',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </span>
                    <span>•</span>
                    <span className="text-emerald-600 dark:text-emerald-400">
                      {activity.pointsBalance.toLocaleString('pt-BR')} pts
                    </span>
                    {activity.dailyEarnings > 0 && (
                      <>
                        <span>•</span>
                        <span className="text-blue-600 dark:text-blue-400">
                          +{activity.dailyEarnings} hoje
                        </span>
                      </>
                    )}
                  </div>

                  {activity.errorMessage && (
                    <p className="text-xs text-red-500">{activity.errorMessage}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
