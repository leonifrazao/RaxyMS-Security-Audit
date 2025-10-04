const FALLBACK_BASE_URL =
  process.env.NEXT_PUBLIC_RAXY_API_URL ?? process.env.RAXY_API_URL ?? ''

interface ApiFetchOptions extends RequestInit {
  parseJson?: boolean
}

export async function apiFetch<T>(path: string, options: ApiFetchOptions = {}): Promise<T> {
  const { parseJson = true, headers, ...init } = options
  const url = resolveUrl(path)

  const response = await fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
    cache: init.cache ?? 'no-store',
  })

  if (!response.ok) {
    const errorText = await extractError(response)
    throw new Error(errorText || `Falha ao comunicar com ${url}`)
  }

  if (!parseJson) {
    return undefined as T
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

export function getApiBaseUrl() {
  return FALLBACK_BASE_URL
}

function resolveUrl(path: string) {
  if (path.startsWith('http://') || path.startsWith('https://')) {
    return path
  }

  if (!FALLBACK_BASE_URL) {
    throw new Error('NEXT_PUBLIC_RAXY_API_URL não configurada.')
  }

  return `${FALLBACK_BASE_URL}${path}`
}

async function extractError(response: Response) {
  try {
    const data = await response.json()
    if (typeof data === 'string') return data
    if (data?.message) return data.message as string
  } catch {
    // ignore
  }
  return response.statusText
}
