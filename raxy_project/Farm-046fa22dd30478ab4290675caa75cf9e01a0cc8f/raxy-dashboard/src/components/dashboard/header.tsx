'use client'

import { useState } from 'react'
import { LogOut, Play, Settings, UserPlus, UsersRound } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { AddAccountDialog } from '@/features/accounts/components/add-account-dialog'
import { useStartAllFarmsMutation } from '@/features/accounts/hooks/use-accounts'
import { ThemeToggle } from '@/components/dashboard/theme-toggle'
import { toast } from '@/hooks/use-toast'

export function Header() {
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const startAll = useStartAllFarmsMutation()

  const handleStartAll = async () => {
    try {
      await startAll.mutateAsync()
      toast({
        title: 'Farms iniciados',
        description: 'Todas as contas elegíveis foram colocadas em processamento.',
      })
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Não foi possível iniciar as contas.'
      toast({
        title: 'Falha ao iniciar farms',
        description: message,
        variant: 'destructive',
      })
    }
  }

  return (
    <header className="sticky top-0 z-20 border-b border-border/60 bg-background/80 backdrop-blur">
      <div className="flex items-center justify-between px-4 py-4 sm:px-6 lg:px-8">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-500">
            <UsersRound className="h-5 w-5" aria-hidden />
          </div>
          <div>
            <h1 className="text-lg font-semibold leading-tight sm:text-xl">Raxy Farm Dashboard</h1>
            <p className="text-sm text-muted-foreground">Controle operacional das contas Microsoft Rewards.</p>
          </div>
          <Badge variant="secondary" className="hidden sm:inline-flex">
            Beta
          </Badge>
        </div>

        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={() => setIsDialogOpen(true)}
            className="hidden sm:inline-flex"
          >
            <UserPlus className="mr-2 h-4 w-4" aria-hidden />
            Nova conta
          </Button>

          <Button
            type="button"
            variant="outline"
            size="icon"
            onClick={() => setIsDialogOpen(true)}
            className="sm:hidden"
          >
            <UserPlus className="h-4 w-4" aria-hidden />
            <span className="sr-only">Adicionar conta</span>
          </Button>

          <Button
            type="button"
            variant="default"
            onClick={handleStartAll}
            disabled={startAll.isPending}
          >
            <Play className="mr-2 h-4 w-4" aria-hidden />
            {startAll.isPending ? 'Iniciando...' : 'Iniciar farms'}
          </Button>

          <ThemeToggle />

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-border/60 bg-card shadow-sm transition hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              >
                <Avatar className="h-9 w-9">
                  <AvatarFallback>RF</AvatarFallback>
                </Avatar>
                <span className="sr-only">Abrir menu do usuário</span>
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="min-w-[12rem]">
              <DropdownMenuLabel>Usuário</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem>
                <Settings className="mr-2 h-4 w-4" aria-hidden />
                Configurações
              </DropdownMenuItem>
              <DropdownMenuItem>
                <LogOut className="mr-2 h-4 w-4" aria-hidden />
                Sair
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
      <AddAccountDialog open={isDialogOpen} onOpenChange={setIsDialogOpen} />
    </header>
  )
}
