export interface ProxyEntry {
  url: string
  country?: string
  tested: boolean
  working: boolean
  latency?: number
}

export interface ProxyBridge {
  id: number
  port: number
  proxy: string
  status: string
}

export interface ProxyStartRequest {
  threads?: number
  amounts?: number
  country?: string
  auto_test?: boolean
  wait?: boolean
}

export interface ProxyTestRequest {
  threads?: number
  country?: string
  verbose?: boolean
  force_refresh?: boolean
  timeout?: number
  force?: boolean
}

export interface ProxyAddRequest {
  proxies: string[]
}

export interface ProxySourcesRequest {
  sources: string[]
}
