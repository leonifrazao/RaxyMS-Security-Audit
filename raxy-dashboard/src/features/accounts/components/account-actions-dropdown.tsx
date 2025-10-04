'use client'

import { useState } from 'react'
import { Loader2, MoreVertical, Pause, Play, Trash2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { toast } from '@/hooks/use-toast'

import {
  useDeleteAccountMutation,
  useStartAccountMutation,
  useStopAccountMutation,
} from '@/features/accounts/hooks/use-accounts'
import { type Account } from '@/features/accounts/types'

export function AccountActionsDropdown({ account }: { account: Account }) {
  const [isAlertOpen, setIsAlertOpen] = useState(false)
  const startAccount = useStartAccountMutation(account.id)
  const stopAccount = useStopAccountMutation(account.id)
  const deleteAccount = useDeleteAccountMutation(account.id)

  const isProcessing =
    startAccount.isPending || stopAccount.isPending || deleteAccount.isPending

  const handleStart = async () => {
    try {
      await startAccount.mutateAsync()
      toast({
        title: 'Execução iniciada',
        description: `A conta ${account.email} foi colocada em execução.`,
      })
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Falha ao iniciar a conta.'
      toast({ title: 'Erro', description: message, variant: 'destructive' })
    }
  }

  const handleStop = async () => {
    try {
      await stopAccount.mutateAsync()
      toast({
        title: 'Execução pausada',
        description: `A conta ${account.email} foi pausada.`,
      })
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Falha ao pausar a conta.'
      toast({ title: 'Erro', description: message, variant: 'destructive' })
    }
  }

  const handleDelete = async () => {
    try {
      await deleteAccount.mutateAsync()
      toast({
        title: 'Conta removida',
        description: `A conta ${account.email} foi removida do painel.`,
      })
      setIsAlertOpen(false)
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Falha ao remover a conta.'
      toast({ title: 'Erro', description: message, variant: 'destructive' })
    }
  }

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button type="button" variant="ghost" size="icon" disabled={isProcessing}>
            <span className="sr-only">Abrir ações da conta</span>
            {isProcessing ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <MoreVertical className="h-4 w-4" aria-hidden />
            )}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-[180px]">
          <DropdownMenuItem onSelect={handleStart} disabled={account.status === 'running'}>
            <Play className="mr-2 h-4 w-4" aria-hidden />
            Iniciar
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={handleStop} disabled={account.status !== 'running'}>
            <Pause className="mr-2 h-4 w-4" aria-hidden />
            Pausar
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            onSelect={(event) => {
              event.preventDefault()
              setIsAlertOpen(true)
            }}
            className="text-destructive focus:text-destructive"
          >
            <Trash2 className="mr-2 h-4 w-4" aria-hidden />
            Remover
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <AlertDialog open={isAlertOpen} onOpenChange={setIsAlertOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remover conta</AlertDialogTitle>
            <AlertDialogDescription>
              Essa ação não pode ser desfeita. A conta será removida permanentemente do dashboard.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} disabled={deleteAccount.isPending}>
              {deleteAccount.isPending ? (
                <span className="flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                  Removendo...
                </span>
              ) : (
                'Confirmar remoção'
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
