'use client'

import {
  type QueryClient,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'

import { apiFetch, getApiBaseUrl } from '@/lib/api-client'

import { fetchAccounts } from '../data/fetch-accounts'
import {
  type Account,
  type AccountStatus,
  type CreateAccountPayload,
} from '../types'

const ACCOUNTS_QUERY_KEY = ['accounts'] as const

type UseAccountsOptions = {
  initialData?: Account[]
}

export function useAccounts({ initialData }: UseAccountsOptions = {}) {
  return useQuery({
    queryKey: ACCOUNTS_QUERY_KEY,
    queryFn: fetchAccounts,
    initialData,
    staleTime: 1000 * 60,
    refetchInterval: 1000 * 60,
  })
}

export function useAddAccountMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (payload: CreateAccountPayload) => {
      const baseUrl = getApiBaseUrl()
      if (!baseUrl) {
        return createMockAccount(payload)
      }

      return apiFetch<Account>('/accounts', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
    },
    onSuccess: (account) => {
      queryClient.setQueryData<Account[]>(ACCOUNTS_QUERY_KEY, (prev = []) => [
        normalizeAccount(account),
        ...prev,
      ])
      queryClient.invalidateQueries({ queryKey: ACCOUNTS_QUERY_KEY })
    },
  })
}

export function useStartAllFarmsMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async () => {
      const baseUrl = getApiBaseUrl()
      if (!baseUrl) {
        const result = simulateBulkStatusChange(queryClient, 'running')
        queryClient.invalidateQueries({ queryKey: ACCOUNTS_QUERY_KEY })
        return result
      }

      await apiFetch('/farms/start-all', { method: 'POST', parseJson: false })
      const result = simulateBulkStatusChange(queryClient, 'running')
      queryClient.invalidateQueries({ queryKey: ACCOUNTS_QUERY_KEY })
      return result
    },
  })
}

export function useStartAccountMutation(accountId: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async () => {
      const baseUrl = getApiBaseUrl()
      if (!baseUrl) {
        const result = simulateStatusChange(queryClient, accountId, 'running')
        queryClient.invalidateQueries({ queryKey: ACCOUNTS_QUERY_KEY })
        return result
      }

      const account = await apiFetch<Account>(`/accounts/${accountId}/start`, {
        method: 'POST',
      })
      const result = updateAccount(queryClient, account)
      queryClient.invalidateQueries({ queryKey: ACCOUNTS_QUERY_KEY })
      return result
    },
  })
}

export function useStopAccountMutation(accountId: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async () => {
      const baseUrl = getApiBaseUrl()
      if (!baseUrl) {
        const result = simulateStatusChange(queryClient, accountId, 'paused')
        queryClient.invalidateQueries({ queryKey: ACCOUNTS_QUERY_KEY })
        return result
      }

      const account = await apiFetch<Account>(`/accounts/${accountId}/stop`, {
        method: 'POST',
      })
      const result = updateAccount(queryClient, account)
      queryClient.invalidateQueries({ queryKey: ACCOUNTS_QUERY_KEY })
      return result
    },
  })
}

export function useDeleteAccountMutation(accountId: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async () => {
      const baseUrl = getApiBaseUrl()
      if (!baseUrl) {
        removeAccountFromCache(queryClient, accountId)
        queryClient.invalidateQueries({ queryKey: ACCOUNTS_QUERY_KEY })
        return
      }

      await apiFetch(`/accounts/${accountId}`, {
        method: 'DELETE',
        parseJson: false,
      })
      removeAccountFromCache(queryClient, accountId)
      queryClient.invalidateQueries({ queryKey: ACCOUNTS_QUERY_KEY })
    },
  })
}

function createMockAccount(payload: CreateAccountPayload): Account {
  return {
    id: crypto.randomUUID(),
    email: payload.email,
    status: 'idle',
    tier: 'Level 1',
    pointsBalance: 0,
    dailyEarnings: 0,
    lastActivity: new Date().toISOString(),
  }
}

function normalizeAccount(account: Account): Account {
  return {
    id: account.id,
    email: account.email,
    alias: account.alias,
    status: account.status,
    tier: account.tier,
    pointsBalance: account.pointsBalance,
    dailyEarnings: account.dailyEarnings,
    lastActivity: account.lastActivity,
    errorMessage: account.errorMessage,
    country: account.country,
  }
}

function updateAccount(queryClient: QueryClient, account: Account) {
  let updated: Account | undefined

  queryClient.setQueryData<Account[]>(ACCOUNTS_QUERY_KEY, (prev = []) => {
    const next = prev.map((item) => {
      if (item.id === account.id) {
        updated = { ...item, ...account }
        return updated
      }
      return item
    })

    if (!prev.some((item) => item.id === account.id)) {
      next.unshift(account)
      updated = account
    }

    return next
  })

  return updated
}

function simulateStatusChange(
  queryClient: QueryClient,
  accountId: string,
  status: AccountStatus
) {
  let updated: Account | undefined
  queryClient.setQueryData<Account[]>(ACCOUNTS_QUERY_KEY, (prev = []) => {
    return prev.map((account) => {
      if (account.id === accountId) {
        updated = { ...account, status }
        return updated
      }
      return account
    })
  })
  return updated
}

function simulateBulkStatusChange(queryClient: QueryClient, status: AccountStatus) {
  return queryClient.setQueryData<Account[]>(ACCOUNTS_QUERY_KEY, (prev = []) =>
    prev.map((account) => ({ ...account, status }))
  )
}

function removeAccountFromCache(queryClient: QueryClient, accountId: string) {
  return queryClient.setQueryData<Account[]>(ACCOUNTS_QUERY_KEY, (prev = []) =>
    prev.filter((account) => account.id !== accountId)
  )
}
