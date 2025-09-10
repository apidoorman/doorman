'use client'

import { fetchJson } from './http'

export async function getJson<T = any>(url: string): Promise<T> {
  return fetchJson<T>(url)
}

function withCsrf(headers: Record<string, string> = {}) {
  try {
    const mod = require('./http') as any
    const cookie = mod.getCookie ? mod.getCookie('csrf_token') : null
    if (cookie) return { 'X-CSRF-Token': cookie, ...headers }
  } catch {}
  return headers
}

export async function postJson<T = any>(url: string, body: any, headers: Record<string, string> = {}): Promise<T> {
  return fetchJson<T>(url, {
    method: 'POST',
    headers: withCsrf({ 'Content-Type': 'application/json', ...headers }),
    body: JSON.stringify(body)
  })
}

export async function putJson<T = any>(url: string, body: any, headers: Record<string, string> = {}): Promise<T> {
  return fetchJson<T>(url, {
    method: 'PUT',
    headers: withCsrf({ 'Content-Type': 'application/json', ...headers }),
    body: JSON.stringify(body)
  })
}

export async function delJson<T = any>(url: string, body?: any, headers: Record<string, string> = {}): Promise<T> {
  return fetchJson<T>(url, {
    method: 'DELETE',
    headers: withCsrf(body ? { 'Content-Type': 'application/json', ...headers } : headers),
    ...(body ? { body: JSON.stringify(body) } : {})
  })
}
