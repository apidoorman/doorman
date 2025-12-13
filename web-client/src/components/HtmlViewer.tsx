'use client'

import React, { useEffect, useState } from 'react'

export default function HtmlViewer({ src }: { src: string }) {
  const [html, setHtml] = useState<string>('Loading...')

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const res = await fetch(src, { cache: 'no-store' })
        const text = await res.text()
        if (!cancelled) setHtml(text)
      } catch (e: any) {
        if (!cancelled) setHtml(`Failed to load: ${e?.message || e}`)
      }
    }
    load()
    return () => { cancelled = true }
  }, [src])

  return (
    <div className="markdown max-w-none" dangerouslySetInnerHTML={{ __html: html }} />
  )
}

