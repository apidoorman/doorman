export function makeApiKey(apiName?: string, apiVersion?: string): string | null {
  if (!apiName || !apiVersion) return null
  return `${apiName}:${apiVersion}`
}

export function getUseProtobuf(apiName?: string, apiVersion?: string): boolean {
  if (typeof window === 'undefined') return false
  const key = makeApiKey(apiName, apiVersion)
  if (!key) return false
  try {
    const v = window.localStorage.getItem(`use_protobuf:${key}`)
    return v === 'true'
  } catch {
    return false
  }
}

export function setUseProtobuf(apiName?: string, apiVersion?: string, enabled?: boolean): void {
  if (typeof window === 'undefined') return
  const key = makeApiKey(apiName, apiVersion)
  if (!key) return
  try {
    if (enabled) window.localStorage.setItem(`use_protobuf:${key}`, 'true')
    else window.localStorage.removeItem(`use_protobuf:${key}`)
  } catch {
    // ignore storage errors
  }
}

