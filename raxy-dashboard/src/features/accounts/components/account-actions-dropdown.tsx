'use client'

import { useState } from 'react'
import { Loader2, MoreVertical, Play } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { toast } from '@/hooks/use-toast'

import {
  useRunAccountMutation,
} from '@/features/accounts/hooks/use-accounts'
import { type Account } from '@/features/accounts/types'

export function AccountActionsDropdown({ account }: { account: Account }) {
  const [isDisabled, setIsDisabled] = useState(false)
  const runAccount = useRunAccountMutation(account)

  const isProcessing = runAccount.isPending

  const handleRun = async () => {
    if (!account.password) {
      setIsDisabled(true)
      toast({
        title: 'Dados ausentes',
        description:
          'A senha desta conta não está disponível pela API. Execute o lote completo para processá-la.',
        variant: 'destructive',
      })
      return
    }
    try {
      await runAccount.mutateAsync()
      toast({
        title: 'Execução agendada',
        description: `A conta ${account.email} foi enviada para processamento.`,
      })
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Falha ao enviar a conta.'
      toast({ title: 'Erro', description: message, variant: 'destructive' })
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button type="button" variant="ghost" size="icon" disabled={isProcessing || isDisabled}>
          <span className="sr-only">Abrir ações da conta</span>
          {isProcessing ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          ) : (
            <MoreVertical className="h-4 w-4" aria-hidden />
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-[200px]">
        <DropdownMenuItem
          onSelect={(event) => {
            event.preventDefault()
            void handleRun()
          }}
          disabled={isProcessing || isDisabled}
        >
          <Play className="mr-2 h-4 w-4" aria-hidden />
          Executar agora
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
