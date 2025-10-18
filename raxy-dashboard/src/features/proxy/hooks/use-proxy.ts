'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch, getApiBaseUrl } from '@/lib/api-client'

import type {
  ProxyBridge,
  ProxyEntry,
  ProxyStartRequest,
  ProxyTestRequest,
} from '../types'

const PROXY_QUERY_KEY = ['proxy'] as const

export function useProxyEntries() {
  return useQuery({
    queryKey: [...PROXY_QUERY_KEY, 'entries'],
    queryFn: async () => {
      const response = await apiFetch<{ entries: ProxyEntry[]; parse_errors: number }>(
        '/api/v1/proxy/entries'
      )
      return response
    },
    staleTime: 1000 * 30,
    refetchInterval: 1000 * 30,
  })
}

export function useProxyBridges() {
  return useQuery({
    queryKey: [...PROXY_QUERY_KEY, 'bridges'],
    queryFn: async () => {
      const response = await apiFetch<{ bridges: ProxyBridge[] }>('/api/v1/proxy/bridges')
      return response.bridges
    },
    staleTime: 1000 * 30,
    refetchInterval: 1000 * 30,
  })
}

export function useProxyStartMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (payload: ProxyStartRequest) => {
      return await apiFetch<{ status: string; bridges: ProxyBridge[] }>('/api/v1/proxy/start', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PROXY_QUERY_KEY })
    },
  })
}

export function useProxyStopMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async () => {
      return await apiFetch<{ status: string }>('/api/v1/proxy/stop', {
        method: 'POST',
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PROXY_QUERY_KEY })
    },
  })
}

export function useProxyTestMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (payload: ProxyTestRequest) => {
      return await apiFetch<{ status: string; total: number; entries: ProxyEntry[] }>(
        '/api/v1/proxy/test',
        {
          method: 'POST',
          body: JSON.stringify(payload),
        }
      )
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PROXY_QUERY_KEY })
    },
  })
}

export function useProxyRotateMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (bridgeId: number) => {
      return await apiFetch<{ status: string }>('/api/v1/proxy/rotate', {
        method: 'POST',
        body: JSON.stringify({ bridge_id: bridgeId }),
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PROXY_QUERY_KEY })
    },
  })
}
