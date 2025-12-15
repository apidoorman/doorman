'use client'

import { useState, useEffect, useRef } from 'react'

interface SearchableSelectProps {
  value: string
  onChange: (value: string) => void
  onAdd?: () => void
  onKeyPress?: (e: React.KeyboardEvent<HTMLInputElement>) => void
  placeholder?: string
  fetchOptions: () => Promise<string[]>
  disabled?: boolean
  className?: string
  addButtonText?: string
}

export default function SearchableSelect({
  value,
  onChange,
  onAdd,
  onKeyPress,
  placeholder = 'Search...',
  fetchOptions,
  disabled = false,
  className = '',
  addButtonText = 'Add'
}: SearchableSelectProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [options, setOptions] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const loadOptions = async () => {
    if (options.length > 0) {
      setIsOpen(true)
      return
    }

    setLoading(true)
    try {
      const data = await fetchOptions()
      setOptions(data)
      setIsOpen(true)
    } catch (err) {
      console.error('Failed to load options:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleInputFocus = () => {
    if (!disabled && !isOpen) {
      loadOptions()
    }
  }

  const handleSelect = (option: string) => {
    onChange(option)
    setIsOpen(false)
  }

  const filteredOptions = options.filter(opt =>
    opt.toLowerCase().includes(value.toLowerCase())
  )

  // Check if current value exists in the options list (case-insensitive)
  const isValidValue = options.length === 0 || options.some(opt => 
    opt.toLowerCase() === value.trim().toLowerCase()
  )

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      <div className="flex gap-2">
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onFocus={handleInputFocus}
          onKeyPress={onKeyPress}
          placeholder={placeholder}
          disabled={disabled}
          className="input flex-1"
        />
        {onAdd && (
          <button
            type="button"
            onClick={onAdd}
            disabled={disabled || !value.trim() || !isValidValue}
            className="btn btn-secondary"
            title={!isValidValue && value.trim() ? 'Please select a value from the list' : ''}
          >
            {addButtonText}
          </button>
        )}
      </div>

      {isOpen && (
        <div className="absolute z-50 w-full mt-1 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-md shadow-lg max-h-48 overflow-y-auto">
          {loading && (
            <div className="p-3 text-center text-sm text-gray-500 dark:text-gray-400">
              Loading...
            </div>
          )}

          {!loading && filteredOptions.length === 0 && (
            <div className="p-3 text-center text-sm text-gray-500 dark:text-gray-400">
              No matches found
            </div>
          )}

          {!loading && filteredOptions.map((option, index) => (
            <button
              key={index}
              type="button"
              onClick={() => handleSelect(option)}
              className="w-full px-3 py-2 text-left text-sm hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-900 dark:text-gray-100"
            >
              {option}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
