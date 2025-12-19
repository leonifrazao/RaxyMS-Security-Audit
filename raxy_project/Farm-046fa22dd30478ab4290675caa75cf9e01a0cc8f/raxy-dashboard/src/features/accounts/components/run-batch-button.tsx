'use client'

import { useState } from 'react'
import { PlayCircle, Loader2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { toast } from '@/hooks/use-toast'

import { useStartAllFarmsMutation } from '@/features/accounts/hooks/use-accounts'
import { type AccountSource } from '@/features/accounts/types'

interface RunBatchButtonProps {
  source: AccountSource
  disabled?: boolean
}

export function RunBatchButton({ source, disabled }: RunBatchButtonProps) {
  const [isRunning, setIsRunning] = useState(false)
  const startAllFarms = useStartAllFarmsMutation(source)

  const handleRun = async () => {
    setIsRunning(true)
    try {
      await startAllFarms.mutateAsync()
      toast({
        title: 'Execução em lote iniciada',
        description: `Todas as contas da fonte "${source}" foram enviadas para processamento.`,
      })
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Falha ao iniciar execução.'
      toast({ title: 'Erro', description: message, variant: 'destructive' })
    } finally {
      setTimeout(() => setIsRunning(false), 2000)
    }
  }

  const isDisabled = disabled || isRunning || startAllFarms.isPending

  return (
    <Button
      onClick={handleRun}
      disabled={isDisabled}
      size="sm"
      className="gap-2"
    >
      {isRunning || startAllFarms.isPending ? (
        <>
          <Loader2 className="h-4 w-4 animate-spin" />
          Processando...
        </>
      ) : (
        <>
          <PlayCircle className="h-4 w-4" />
          Executar tudo
        </>
      )}
    </Button>
  )
}
