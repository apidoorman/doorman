"use client"

import React, { useState } from 'react'

interface InfoTooltipProps {
  text: string
  className?: string
}

export default function InfoTooltip({ text, className }: InfoTooltipProps) {
  const [open, setOpen] = useState(false)
  return (
    <span className={`relative inline-flex items-center ${className || ''}`}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        type="button"
        aria-label="Help"
        className="ml-1 inline-flex items-center justify-center h-4 w-4 rounded-full bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-200 hover:bg-gray-300 dark:hover:bg-gray-600 focus:outline-none"
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
      >
        <svg className="h-3 w-3" viewBox="0 0 20 20" fill="currentColor" aria-hidden>{}
          <path fillRule="evenodd" d="M18 10A8 8 0 11.001 9.999 8 8 0 0118 10zM9 9a1 1 0 112 0v5a1 1 0 11-2 0V9zm1-6a1.5 1.5 0 100 3 1.5 1.5 0 000-3z" clipRule="evenodd"/>
        </svg>
      </button>
      {open && (
        <div className="absolute z-20 mt-2 w-64 p-2 text-xs rounded-md shadow-lg bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-200">
          {text}
        </div>
      )}
    </span>
  )
}

