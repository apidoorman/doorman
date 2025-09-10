export function getCookie(name: string): string | null {
  if (typeof document === 'undefined') return null
  const match = document.cookie.split('; ').find(c => c.startsWith(name + '='))
  return match ? decodeURIComponent(match.split('=')[1]) : null
}

export async function fetchJson<T = any>(url: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...(init.headers as any)
  }
  const csrf = getCookie('csrf_token')
  if (csrf) headers['X-CSRF-Token'] = csrf

  const resp = await fetch(url, {
    credentials: 'include',
    ...init,
    headers
  })
  const data = await resp.json().catch(() => ({}))
  const unwrapped = (data && typeof data === 'object' && 'response' in data) ? data.response : data
  if (!resp.ok) {
    const msg = (unwrapped && (unwrapped.error_message || unwrapped.message)) || resp.statusText
    throw new Error(msg)
  }
  return unwrapped as T
}

