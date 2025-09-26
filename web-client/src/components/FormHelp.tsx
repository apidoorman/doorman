"use client"

import React from 'react'

interface Props {
  docHref: string
  children: React.ReactNode
  className?: string
}

export default function FormHelp({ docHref, children, className }: Props) {
  return (
    <div className={`text-xs text-gray-600 dark:text-gray-400 flex items-center gap-2 ${className||''}`}>
      <svg className="h-4 w-4 text-gray-500 dark:text-gray-400" viewBox="0 0 20 20" fill="currentColor" aria-hidden>
        <path fillRule="evenodd" d="M18 10A8 8 0 11.001 9.999 8 8 0 0118 10zM9 9a1 1 0 112 0v5a1 1 0 11-2 0V9zm1-6a1.5 1.5 0 100 3 1.5 1.5 0 000-3z" clipRule="evenodd"/>
      </svg>
      <span>{children}</span>
      <a href={docHref} target="_blank" rel="noreferrer" className="text-primary-600 hover:text-primary-700 dark:text-primary-400 underline">
        Learn more
      </a>
    </div>
  )
}

