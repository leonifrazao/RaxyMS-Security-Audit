'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch, getApiBaseUrl } from '@/lib/api-client'

import { fetchAccounts, buildProfileId } from '../data/fetch-accounts'
import {
  type Account,
  type AccountSource,
  type CreateAccountPayload,
} from '../types'

const ACCOUNTS_QUERY_KEY = ['accounts'] as const
const DEFAULT_EXECUTOR_ACTIONS = ['login', 'rewards', 'bing', 'flyout'] as const

type UseAccountsOptions = {
  initialData?: Account[]
  source: AccountSource
}

export function useAccounts({ initialData, source }: UseAccountsOptions) {
  return useQuery({
    queryKey: [...ACCOUNTS_QUERY_KEY, source],
    queryFn: () => fetchAccounts(source),
    initialData: source === 'file' ? initialData : undefined,
    staleTime: 1000 * 60,
    refetchInterval: 1000 * 60,
  })
}

export function useAddAccountMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (payload: CreateAccountPayload) => {
      await apiFetch('/api/v1/executor/run', {
        method: 'POST',
        body: JSON.stringify({
          source: 'manual',
          actions: DEFAULT_EXECUTOR_ACTIONS,
          accounts: [toExecutorAccount(payload)],
        }),
        parseJson: false,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ACCOUNTS_QUERY_KEY })
    },
  })
}

export function useStartAllFarmsMutation(source: AccountSource = 'file') {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async () => {
      await apiFetch('/api/v1/executor/run', {
        method: 'POST',
        body: JSON.stringify({
          source,
          actions: DEFAULT_EXECUTOR_ACTIONS,
        }),
        parseJson: false,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ACCOUNTS_QUERY_KEY })
    },
  })
}

export function useRunAccountMutation(account: Account) {
  return useMutation({
    mutationFn: async () => {
      await apiFetch('/api/v1/executor/run', {
        method: 'POST',
        body: JSON.stringify({
          source: 'manual',
          actions: DEFAULT_EXECUTOR_ACTIONS,
          accounts: [toExecutorAccount(account)],
        }),
        parseJson: false,
      })
    },
  })
}

function toExecutorAccount(account: CreateAccountPayload | Account) {
  const email = account.email
  const password = account.password ?? ''
  if (!password) {
    throw new Error('A API não retornou senha para esta conta.')
  }

  const proxyValue = 'proxy' in account ? account.proxy : undefined
  const profileId =
    'profileId' in account && account.profileId
      ? account.profileId
      : buildProfileId(email)

  return {
    email,
    password,
    profile_id: profileId,
    proxy: proxyValue ?? undefined,
  }
}
