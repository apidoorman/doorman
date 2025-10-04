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
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="fixed inset-0 bg-black/50" onClick={onCancel}></div>
      <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-md w-full mx-4 relative z-10">
        <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-4">{title}</h3>
        <div className="text-gray-600 dark:text-gray-400 mb-4 text-sm">
          {message}
        </div>
        {typeof requireTextMatch === 'string' && (
          <div className="mb-4">
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">Please type <strong>{requireTextMatch}</strong> to confirm.</p>
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              className="input w-full"
              placeholder={inputPlaceholder || 'Type to confirm'}
            />
          </div>
        )}
        <div className="flex gap-2 justify-end">
          <button className="btn btn-secondary" onClick={onCancel} disabled={loading}>{cancelLabel}</button>
          <button className="btn btn-primary" onClick={onConfirm} disabled={confirmDisabled}>{confirmLabel}</button>
        </div>
      </div>
    </div>
  )
}
