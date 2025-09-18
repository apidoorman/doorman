'use client'

import React, { createContext, useCallback, useContext, useMemo, useState } from 'react'

type ToastKind = 'success' | 'error' | 'info' | 'warning'

export type Toast = {
  id: string
  kind: ToastKind
  message: string
  timeoutMs?: number
}

type ToastContextType = {
  push: (t: Omit<Toast, 'id'>) => void
  success: (message: string, timeoutMs?: number) => void
  error: (message: string, timeoutMs?: number) => void
  info: (message: string, timeoutMs?: number) => void
  warning: (message: string, timeoutMs?: number) => void
}

const ToastContext = createContext<ToastContextType | null>(null)

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<Toast[]>([])

  const remove = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  const push = useCallback((t: Omit<Toast, 'id'>) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2)}`
    const toast: Toast = { id, timeoutMs: 2500, ...t }
    setToasts(prev => [...prev, toast])
    if (toast.timeoutMs && toast.timeoutMs > 0) {
      setTimeout(() => remove(id), toast.timeoutMs)
    }
  }, [remove])

  const api = useMemo<ToastContextType>(() => ({
    push,
    success: (message, timeoutMs) => push({ kind: 'success', message, timeoutMs }),
    error: (message, timeoutMs) => push({ kind: 'error', message, timeoutMs }),
    info: (message, timeoutMs) => push({ kind: 'info', message, timeoutMs }),
    warning: (message, timeoutMs) => push({ kind: 'warning', message, timeoutMs }),
  }), [push])

  return (
    <ToastContext.Provider value={api}>
      {children}
      <ToastContainer toasts={toasts} onClose={remove} />
    </ToastContext.Provider>
  )
}

export function useToast(): ToastContextType {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}

export const ToastContainer: React.FC<{ toasts: Toast[]; onClose: (id: string) => void }> = ({ toasts, onClose }) => {
  return (
    <div className="fixed top-4 right-4 z-[1000] space-y-2">
      {toasts.map(t => (
        <div key={t.id}
          className={[
            'min-w-[220px] max-w-sm shadow-lg rounded-md px-4 py-3 text-sm flex items-start gap-2',
            'bg-white dark:bg-gray-800 border',
            t.kind === 'success' ? 'border-green-200 text-green-800 dark:border-green-800 dark:text-green-200' : '',
            t.kind === 'error' ? 'border-red-200 text-red-800 dark:border-red-800 dark:text-red-200' : '',
            t.kind === 'info' ? 'border-blue-200 text-blue-800 dark:border-blue-800 dark:text-blue-200' : '',
            t.kind === 'warning' ? 'border-yellow-200 text-yellow-800 dark:border-yellow-800 dark:text-yellow-200' : ''
          ].join(' ')}>
          <span className="mt-0.5">
            {t.kind === 'success' && (
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
            )}
            {t.kind === 'error' && (
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
            )}
            {t.kind === 'info' && (
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12A9 9 0 113 12a9 9 0 0118 0z" /></svg>
            )}
            {t.kind === 'warning' && (
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M4.93 19h14.14a2 2 0 001.74-3L13.74 5a2 2 0 00-3.48 0L3.19 16a2 2 0 001.74 3z" /></svg>
            )}
          </span>
          <div className="flex-1">{t.message}</div>
          <button className="ml-2 opacity-70 hover:opacity-100" onClick={() => onClose(t.id)} aria-label="Close">
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>
      ))}
    </div>
  )
}

