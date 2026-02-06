'use client'

import React from 'react'

interface PaginationProps {
  page: number
  pageSize: number
  onPageChange: (page: number) => void
  onPageSizeChange: (size: number) => void
  hasNext?: boolean
  className?: string
}

export default function Pagination({ page, pageSize, onPageChange, onPageSizeChange, hasNext = false, className = '' }: PaginationProps) {
  const sizes = [10, 25, 50]
  const canPrev = page > 1
  const canNext = !!hasNext
  return (
    <div className={`flex items-center justify-between py-3 ${className}`}>
      <div className="flex items-center gap-2">
        <span className="text-sm text-gray-600 dark:text-gray-400">Rows per page:</span>
        <select
          className="input h-9 w-24"
          value={pageSize}
          onChange={e => onPageSizeChange(parseInt(e.target.value, 10))}
        >
          {sizes.map(s => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>
      <div className="flex items-center gap-3">
        <span className="text-sm text-gray-600 dark:text-gray-400">Page {page}</span>
        <div className="flex items-center gap-2">
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => canPrev && onPageChange(page - 1)}
            disabled={!canPrev}
          >
            Prev
          </button>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => canNext && onPageChange(page + 1)}
            disabled={!canNext}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  )
}
