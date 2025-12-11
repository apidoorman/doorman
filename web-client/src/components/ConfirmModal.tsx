'use client'

import React, { useEffect, useState } from 'react'

interface ConfirmModalProps {
  open: boolean
  title: string
  message: string | React.ReactNode
  confirmLabel?: string
  cancelLabel?: string
  onConfirm: () => void
  onCancel: () => void
  loading?: boolean
  requireTextMatch?: string
  inputPlaceholder?: string
}

export default function ConfirmModal({
  open,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  onConfirm,
  onCancel,
  loading = false,
  requireTextMatch,
  inputPlaceholder
}: ConfirmModalProps) {
  const [input, setInput] = useState('')
  useEffect(() => { if (!open) setInput('') }, [open])

  if (!open) return null

  const confirmDisabled = loading || (requireTextMatch ? input !== (requireTextMatch || '') : false)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" onClick={onCancel}>
      <div className="absolute inset-0 bg-black/50" />
      <div className="relative max-w-md mx-auto bg-white dark:bg-dark-surface border border-gray-200 dark:border-white/[0.12] rounded-lg shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="px-4 py-3 border-b border-gray-200 dark:border-white/[0.08] flex items-center justify-between">
          <div className="text-[14px] font-medium text-gray-900 dark:text-white/90">{title}</div>
          <button onClick={onCancel} className="text-gray-500 dark:text-white/60 hover:text-gray-700 dark:hover:text-white/80" aria-label="Close">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg>
          </button>
        </div>
        <div className="p-4 space-y-3">
          <div className="text-[13px] text-gray-700 dark:text-white/80">
            {message}
          </div>
          {typeof requireTextMatch === 'string' && (
            <div>
              <div className="text-[12px] text-gray-600 dark:text-white/60 mb-2">Type <span className="font-medium">{requireTextMatch}</span> to confirm</div>
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                className="input w-full"
                placeholder={inputPlaceholder || 'Type to confirm'}
              />
            </div>
          )}
          <div className="flex items-center justify-end gap-2 pt-1">
            <button onClick={onCancel} disabled={loading} className="px-3 py-1.5 bg-transparent border border-gray-300 dark:border-white/[0.12] rounded-sm text-[12px] text-gray-700 dark:text-white/80 hover:bg-gray-50 dark:hover:bg-white/5">{cancelLabel}</button>
            <button onClick={onConfirm} disabled={confirmDisabled} className={`px-3 py-1.5 rounded-sm text-[12px] font-medium ${confirmDisabled ? 'bg-gray-200 dark:bg-white/20 text-gray-500 dark:text-white/40 cursor-not-allowed' : 'bg-primary-600 dark:bg-[#e5e5e5] text-white dark:text-[#1a1a1a] hover:bg-primary-700 dark:hover:bg-white'}`}>{confirmLabel}</button>
          </div>
        </div>
      </div>
    </div>
  )
}
