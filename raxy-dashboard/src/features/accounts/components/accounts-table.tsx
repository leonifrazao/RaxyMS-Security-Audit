'use client'

import { useEffect, useMemo, useState } from 'react'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import { Loader2, RefreshCw } from 'lucide-react'
import type { CheckedState } from '@radix-ui/react-checkbox'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Separator } from '@/components/ui/separator'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

import { useAccounts } from '@/features/accounts/hooks/use-accounts'
import { type Account, type AccountStatus, type AccountSource } from '@/features/accounts/types'

import { AccountActionsDropdown } from './account-actions-dropdown'

interface AccountsTableProps {
  initialData: Account[]
  initialSource?: AccountSource
}

const SOURCE_OPTIONS: Array<{ label: string; value: AccountSource }> = [
  { label: 'Arquivo (users.txt)', value: 'file' },
  { label: 'Banco (Supabase)', value: 'database' },
]

export function AccountsTable({ initialData, initialSource = 'file' }: AccountsTableProps) {
  const searchParams = useSearchParams()
  const router = useRouter()
  const pathname = usePathname()

  const [selection, setSelection] = useState<Set<string>>(new Set())
  const [emailFilter, setEmailFilter] = useState(() => searchParams.get('email') ?? '')
  const [source, setSource] = useState<AccountSource>(() =>
    searchParams.get('source') === 'database' ? 'database' : initialSource
  )

  const accountsQuery = useAccounts({
    initialData: source === initialSource ? initialData : undefined,
    source,
  })

  const accounts = useMemo(() => {
    const data = accountsQuery.data ?? []
    if (!emailFilter) {
      return data
    }
    const normalizedFilter = emailFilter.trim().toLowerCase()
    return data.filter((account) =>
      account.email.toLowerCase().includes(normalizedFilter)
    )
  }, [accountsQuery.data, emailFilter])

  useEffect(() => {
    setSelection((prev) => {
      const validIds = new Set(accounts.map((account) => account.id))
      const next = new Set<string>()
      prev.forEach((id) => {
        if (validIds.has(id)) {
          next.add(id)
        }
      })
      return next
    })
  }, [accounts])

  useEffect(() => {
    setEmailFilter(searchParams.get('email') ?? '')
    const querySource = searchParams.get('source') === 'database' ? 'database' : 'file'
    setSource(querySource)
  }, [searchParams])

  useEffect(() => {
    const timer = setTimeout(() => {
      const params = new URLSearchParams(searchParams.toString())
      if (emailFilter) {
        params.set('email', emailFilter)
      } else {
        params.delete('email')
      }
      params.set('source', source)
      const query = params.toString()
      router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false })
    }, 250)

    return () => clearTimeout(timer)
  }, [emailFilter, pathname, router, searchParams, source])

  const toggleSelection = (id: string) => {
    setSelection((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  const toggleAllSelection = (state: CheckedState) => {
    setSelection(() => {
      if (state === true) {
        return new Set(accounts.map((account) => account.id))
      }
      return new Set()
    })
  }

  const resetFilters = () => {
    setEmailFilter('')
    setSelection(new Set())
    setSource('file')
    router.replace(pathname, { scroll: false })
  }

  const isLoading = accountsQuery.isLoading && !accountsQuery.data?.length
  const isEmpty = !isLoading && accounts.length === 0

  return (
    <section className="space-y-4">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold">Contas</h2>
          <p className="text-sm text-muted-foreground">
            Visualize o status das contas e dispare ações pontuais.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1 rounded-full border border-border/60 p-1 text-xs font-medium">
            {SOURCE_OPTIONS.map((option) => {
              const isActive = source === option.value
              return (
                <Button
                  key={option.value}
                  type="button"
                  size="sm"
                  variant={isActive ? 'default' : 'ghost'}
                  className="h-7 rounded-full px-3 text-xs"
                  onClick={() => setSource(option.value)}
                >
                  {option.label}
                </Button>
              )
            })}
          </div>

          <div className="flex items-center gap-2">
            <Input
              value={emailFilter}
              onChange={(event) => setEmailFilter(event.target.value)}
              placeholder="Buscar por e-mail"
              className="w-[220px]"
            />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={() => accountsQuery.refetch()}
              disabled={accountsQuery.isFetching}
            >
              {accountsQuery.isFetching ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
              ) : (
                <RefreshCw className="h-4 w-4" aria-hidden />
              )}
              <span className="sr-only">Atualizar lista</span>
            </Button>
          </div>

          {(emailFilter || selection.size > 0) && (
            <Button type="button" variant="outline" onClick={resetFilters}>
              Limpar filtros
            </Button>
          )}
        </div>
      </header>

      {selection.size > 0 ? (
        <div className="rounded-lg border border-dashed border-emerald-500/40 bg-emerald-500/5 px-4 py-2 text-sm text-emerald-500">
          {selection.size} conta(s) selecionada(s)
        </div>
      ) : null}

      <div className="hidden rounded-lg border bg-card shadow-sm md:block">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[48px]">
                <Checkbox
                  checked={
                    selection.size === accounts.length && accounts.length > 0
                      ? true
                      : selection.size > 0
                      ? 'indeterminate'
                      : false
                  }
                  onCheckedChange={toggleAllSelection}
                  aria-label="Selecionar todas as contas"
                />
              </TableHead>
              <TableHead>E-mail</TableHead>
              <TableHead>Perfil</TableHead>
              <TableHead>Origem</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Tier</TableHead>
              <TableHead className="text-right">Saldo</TableHead>
              <TableHead className="text-right">Hoje</TableHead>
              <TableHead>Última atividade</TableHead>
              <TableHead className="text-right">Ações</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <LoadingRows />
            ) : (
              accounts.map((account) => (
                <TableRow key={account.id} className="hover:bg-muted/40">
                  <TableCell>
                    <Checkbox
                      checked={selection.has(account.id)}
                      onCheckedChange={() => toggleSelection(account.id)}
                      aria-label={`Selecionar conta ${account.email}`}
                    />
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-col">
                      <span className="font-medium">{account.email}</span>
                      {account.alias ? (
                        <span className="text-xs text-muted-foreground">{account.alias}</span>
                      ) : null}
                    </div>
                  </TableCell>
                  <TableCell>
                    <span className="text-xs text-muted-foreground">{account.profileId}</span>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="capitalize">
                      {sourceLabel(account.source)}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={account.status} />
                  </TableCell>
                  <TableCell>{account.tier}</TableCell>
                  <TableCell className="text-right font-medium">
                    {formatCurrency(account.pointsBalance)}
                  </TableCell>
                  <TableCell className="text-right text-sm text-muted-foreground">
                    {formatCurrency(account.dailyEarnings)}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {formatRelativeDate(account.lastActivity)}
                  </TableCell>
                  <TableCell className="text-right">
                    <AccountActionsDropdown account={account} />
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
        {isEmpty ? <EmptyState /> : null}
      </div>

      <div className="grid gap-3 md:hidden">
        {isLoading ? (
          <MobileLoadingCards />
        ) : isEmpty ? (
          <EmptyState />
        ) : (
          accounts.map((account) => (
            <Card key={account.id} className="border-border/60 bg-card/70 backdrop-blur">
              <CardContent className="space-y-4 p-4">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-medium">{account.email}</p>
                    <p className="text-xs text-muted-foreground">{account.profileId}</p>
                  </div>
                  <StatusBadge status={account.status} />
                </div>

                <div className="grid grid-cols-2 gap-3 text-sm text-muted-foreground">
                  <InfoPair label="Tier" value={account.tier} />
                  <InfoPair label="Origem" value={sourceLabel(account.source)} />
                  <InfoPair label="Última atividade" value={formatRelativeDate(account.lastActivity)} />
                  <InfoPair label="Saldo" value={formatCurrency(account.pointsBalance)} />
                  <InfoPair label="Hoje" value={formatCurrency(account.dailyEarnings)} />
                </div>

                <Separator />

                <div className="flex items-center justify-between">
                  <Checkbox
                    checked={selection.has(account.id)}
                    onCheckedChange={() => toggleSelection(account.id)}
                    aria-label={`Selecionar conta ${account.email}`}
                  />
                  <AccountActionsDropdown account={account} />
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>

      {accountsQuery.isError ? (
        <Card className="border-destructive/40 bg-destructive/10">
          <CardContent className="p-4 text-sm text-destructive">
            Não foi possível obter as contas. Tente novamente em alguns instantes.
          </CardContent>
        </Card>
      ) : null}
    </section>
  )
}

function formatCurrency(value: number) {
  return new Intl.NumberFormat('pt-BR').format(value)
}

function sourceLabel(source: AccountSource) {
  switch (source) {
    case 'database':
      return 'Banco de dados'
    case 'manual':
      return 'Manual'
    default:
      return 'Arquivo'
  }
}

function formatRelativeDate(isoDate: string) {
  if (!isoDate) return '—'
  const date = new Date(isoDate)
  if (Number.isNaN(date.getTime())) {
    return '—'
  }
  return new Intl.DateTimeFormat('pt-BR', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(date)
}

const STATUS_MAP: Record<
  AccountStatus,
  {
    label: string
    variant: 'default' | 'secondary' | 'destructive' | 'outline'
    tone?: string
  }
> = {
  idle: { label: 'Pronto', variant: 'secondary' },
  running: { label: 'Executando', variant: 'default', tone: 'bg-emerald-500/10 text-emerald-500' },
  paused: { label: 'Pausado', variant: 'outline' },
  completed: { label: 'Concluído', variant: 'secondary' },
  error: { label: 'Erro', variant: 'destructive' },
}

function StatusBadge({ status }: { status: AccountStatus }) {
  const config = STATUS_MAP[status]
  return (
    <Badge variant={config.variant} className={cn('capitalize', config.tone)}>
      {config.label}
    </Badge>
  )
}

function InfoPair({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground/80">{label}</p>
      <p className="font-medium text-foreground">{value}</p>
    </div>
  )
}

function LoadingRows() {
  return (
    <>
      {Array.from({ length: 5 }).map((_, index) => (
        <TableRow key={index}>
          {Array.from({ length: 8 }).map((__, cellIndex) => (
            <TableCell key={cellIndex}>
              <Skeleton className="h-4 w-full" />
            </TableCell>
          ))}
        </TableRow>
      ))}
    </>
  )
}

function MobileLoadingCards() {
  return (
    <>
      {Array.from({ length: 3 }).map((_, index) => (
        <Card key={index} className="border-border/60 bg-card/70">
          <CardContent className="space-y-3 p-4">
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-4 w-1/2" />
            <div className="grid grid-cols-2 gap-3">
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-full" />
            </div>
            <Skeleton className="h-8 w-full" />
          </CardContent>
        </Card>
      ))}
    </>
  )
}

function EmptyState() {
  return (
    <div className="flex min-h-[180px] flex-col items-center justify-center gap-2 p-6 text-center text-sm text-muted-foreground">
      <p>Nenhuma conta encontrada com os filtros atuais.</p>
      <p>Ajuste sua busca ou adicione uma nova conta.</p>
    </div>
  )
}
