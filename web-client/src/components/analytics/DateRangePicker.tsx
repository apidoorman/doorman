'use client'

import React, { useState } from 'react'

interface DateRangePickerProps {
  startDate: string
  endDate: string
  onStartDateChange: (date: string) => void
  onEndDateChange: (date: string) => void
  onApply: () => void
  onClear: () => void
}

export default function DateRangePicker({
  startDate,
  endDate,
  onStartDateChange,
  onEndDateChange,
  onApply,
  onClear
}: DateRangePickerProps) {
  const [isOpen, setIsOpen] = useState(false)

  // Quick date range presets
  const applyPreset = (preset: string) => {
    const now = new Date()
    const end = now.toISOString().slice(0, 16)
    let start = ''

    switch (preset) {
      case '1h':
        start = new Date(now.getTime() - 3600000).toISOString().slice(0, 16)
        break
      case '24h':
        start = new Date(now.getTime() - 86400000).toISOString().slice(0, 16)
        break
      case '7d':
        start = new Date(now.getTime() - 604800000).toISOString().slice(0, 16)
        break
      case '30d':
        start = new Date(now.getTime() - 2592000000).toISOString().slice(0, 16)
        break
    }

    onStartDateChange(start)
    onEndDateChange(end)
  }

  const formatDateDisplay = (dateStr: string): string => {
    if (!dateStr) return 'Not set'
    const date = new Date(dateStr)
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  return (
    <div className="relative">
      {/* Trigger Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-4 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
      >
        <svg className="h-5 w-5 text-gray-500 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
        <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
          {startDate && endDate ? (
            <>
              {formatDateDisplay(startDate)} - {formatDateDisplay(endDate)}
            </>
          ) : (
            'Select Date Range'
          )}
        </span>
        <svg className={`h-4 w-4 text-gray-500 transition-transform ${isOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Dropdown Panel */}
      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsOpen(false)}
          />

          {/* Panel */}
          <div className="absolute right-0 mt-2 w-96 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 z-20">
            <div className="p-4 space-y-4">
              {/* Quick Presets */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Quick Select
                </label>
                <div className="grid grid-cols-4 gap-2">
                  {[
                    { label: 'Last Hour', value: '1h' },
                    { label: 'Last 24h', value: '24h' },
                    { label: 'Last 7d', value: '7d' },
                    { label: 'Last 30d', value: '30d' }
                  ].map((preset) => (
                    <button
                      key={preset.value}
                      onClick={() => applyPreset(preset.value)}
                      className="px-3 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
                    >
                      {preset.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Custom Date Range */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Custom Range
                </label>
                <div className="space-y-3">
                  <div>
                    <label className="block text-xs text-gray-600 dark:text-gray-400 mb-1">
                      Start Date & Time
                    </label>
                    <input
                      type="datetime-local"
                      value={startDate}
                      onChange={(e) => onStartDateChange(e.target.value)}
                      className="input w-full"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-600 dark:text-gray-400 mb-1">
                      End Date & Time
                    </label>
                    <input
                      type="datetime-local"
                      value={endDate}
                      onChange={(e) => onEndDateChange(e.target.value)}
                      className="input w-full"
                    />
                  </div>
                </div>
              </div>

              {/* Actions */}
              <div className="flex items-center justify-between pt-3 border-t border-gray-200 dark:border-gray-700">
                <button
                  onClick={() => {
                    onClear()
                    setIsOpen(false)
                  }}
                  className="text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200"
                >
                  Clear
                </button>
                <div className="flex gap-2">
                  <button
                    onClick={() => setIsOpen(false)}
                    className="btn btn-outline btn-sm"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => {
                      onApply()
                      setIsOpen(false)
                    }}
                    className="btn btn-primary btn-sm"
                  >
                    Apply
                  </button>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
