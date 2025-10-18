'use client'

import { useState } from 'react'
import { Activity, Loader2, Play, Square, RefreshCw } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { toast } from '@/hooks/use-toast'

import {
  useProxyBridges,
  useProxyEntries,
  useProxyStartMutation,
  useProxyStopMutation,
  useProxyTestMutation,
  useProxyRotateMutation,
} from '../hooks/use-proxy'

export function ProxyManagerCard() {
  const [isTesting, setIsTesting] = useState(false)
  const entriesQuery = useProxyEntries()
  const bridgesQuery = useProxyBridges()
  const startMutation = useProxyStartMutation()
  const stopMutation = useProxyStopMutation()
  const testMutation = useProxyTestMutation()

  const handleStart = async () => {
    try {
      await startMutation.mutateAsync({
        threads: 200,
        auto_test: true,
        country: 'US',
      })
      toast({
        title: 'Proxies iniciados',
        description: 'As pontes de proxy foram criadas com sucesso.',
      })
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Falha ao iniciar proxies.'
      toast({ title: 'Erro', description: message, variant: 'destructive' })
    }
  }

  const handleStop = async () => {
    try {
      await stopMutation.mutateAsync()
      toast({
        title: 'Proxies parados',
        description: 'Todas as pontes de proxy foram encerradas.',
      })
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Falha ao parar proxies.'
      toast({ title: 'Erro', description: message, variant: 'destructive' })
    }
  }

  const handleTest = async () => {
    setIsTesting(true)
    try {
      const result = await testMutation.mutateAsync({
        threads: 200,
        country: 'US',
        timeout: 10,
      })
      toast({
        title: 'Teste concluído',
        description: `${result.total} proxies testados com sucesso.`,
      })
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Falha ao testar proxies.'
      toast({ title: 'Erro', description: message, variant: 'destructive' })
    } finally {
      setIsTesting(false)
    }
  }

  const entries = entriesQuery.data?.entries ?? []
  const bridges = bridgesQuery.data ?? []
  const workingProxies = entries.filter((e) => e.working).length

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              Gerenciador de Proxies
            </CardTitle>
            <CardDescription>Controle e monitore o pool de proxies</CardDescription>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleTest}
              disabled={isTesting || testMutation.isPending}
            >
              {isTesting || testMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4" />
              )}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleStart}
              disabled={startMutation.isPending || bridges.length > 0}
            >
              {startMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleStop}
              disabled={stopMutation.isPending || bridges.length === 0}
            >
              {stopMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Square className="h-4 w-4" />
              )}
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {entriesQuery.isLoading ? (
          <ProxyStatsSkeleton />
        ) : (
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="space-y-1">
              <p className="text-sm text-muted-foreground">Total de proxies</p>
              <p className="text-2xl font-bold">{entries.length}</p>
            </div>
            <div className="space-y-1">
              <p className="text-sm text-muted-foreground">Proxies funcionais</p>
              <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">
                {workingProxies}
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-sm text-muted-foreground">Pontes ativas</p>
              <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                {bridges.length}
              </p>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function ProxyStatsSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-3">
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="space-y-2">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-8 w-16" />
        </div>
      ))}
    </div>
  )
}
