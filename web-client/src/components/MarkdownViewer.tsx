'use client'

import React, { useEffect, useState } from 'react'

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function escapeRegExp(str: string) {
  return str.replace(/[.*+?^${}()|[\\]\\]/g, '\\$&')
}

function renderMarkdown(md: string, searchTerm?: string): string {
  const lines = md.replaceAll('\r\n', '\n').split('\n')
  let html = ''
  let inCode = false
  let inList = false
  let inOList = false
  let pOpen = false
  let inTable = false
  let tableHeader: string[] | null = null

  function closeList() {
    if (inList) {
      html += '</ul>'
      inList = false
    }
    if (inOList) {
      html += '</ol>'
      inOList = false
    }
  }
  function closeParagraph() {
    if (pOpen) {
      html += '</p>'
      pOpen = false
    }
  }
  function closeTable() {
    if (inTable) {
      html += '</tbody></table>'
      inTable = false
      tableHeader = null
    }
  }

  for (const raw of lines) {
    const line = raw.trimEnd()
    if (line.startsWith('```')) {
      closeTable()
      closeList()
      closeParagraph()
      if (!inCode) {
        const lang = line.slice(3).trim().toLowerCase()
        const langClass = lang ? ` language-${escapeHtml(lang)}` : ''
        html += `<pre class="overflow-auto rounded bg-gray-50 dark:bg-[#0f172a] p-3 text-[12px]"><code class="${langClass}">`
        inCode = true
      } else {
        html += '</code></pre>'
        inCode = false
      }
      continue
    }
    if (inCode) {
      html += escapeHtml(raw) + '\n'
      continue
    }

    if (line === '') {
      closeTable()
      closeList()
      closeParagraph()
      continue
    }

    // Blockquote
    if (line.startsWith('>')) {
      closeList(); closeTable(); closeParagraph()
      const text = line.replace(/^>\s?/, '')
      html += `<blockquote class="border-l-4 pl-3 my-2 text-gray-600 dark:text-white/70">${escapeHtml(text)}</blockquote>`
      continue
    }

    const m = line.match(/^(#{1,6})\s+(.*)$/)
    if (m) {
      closeList(); closeTable()
      closeParagraph()
      const level = m[1].length
      const headingText = m[2].trim()
      const id = headingText.toLowerCase().replace(/[^a-z0-9\s-]/g, '').replace(/\s+/g, '-').slice(0, 64)
      html += `<h${level} id="${id}" class="mt-4 mb-2 font-semibold">${escapeHtml(headingText)}</h${level}>`
      continue
    }

    const lm = line.match(/^[-*]\s+(.*)$/)
    if (lm) {
      if (!inList) {
        closeParagraph(); closeTable()
        html += '<ul class="list-disc pl-6 my-2">'
        inList = true
      }
      html += `<li>${escapeHtml(lm[1])}</li>`
      continue
    }

    const om = line.match(/^\d+\.[\)\s]+(.*)$/)
    if (om) {
      if (!inOList) {
        closeParagraph(); closeTable()
        html += '<ol class="list-decimal pl-6 my-2">'
        inOList = true
      }
      html += `<li>${escapeHtml(om[1])}</li>`
      continue
    }

    // Tables: header line with | then separator with dashes
    if (line.includes('|')) {
      const parts = line.split('|').map(s => s.trim()).filter((_, i, arr) => !(i === 0 && arr[0] === '') && !(i === arr.length - 1 && arr[arr.length - 1] === ''))
      if (parts.length > 1 && tableHeader === null) {
        // Look ahead for separator (---)
        tableHeader = parts
        continue
      }
      if (tableHeader && parts.every(c => /^:?-{3,}:?$/.test(c) || c === '')) {
        // Start table
        closeParagraph(); closeList()
        html += '<table class="table-auto border-collapse my-3 w-full"><thead><tr>'
        for (const h of tableHeader) html += `<th class="border px-2 py-1 text-left">${escapeHtml(h)}</th>`
        html += '</tr></thead><tbody>'
        inTable = true
        tableHeader = []
        continue
      }
      if (inTable && parts.length > 0) {
        html += '<tr>'
        for (const c of parts) html += `<td class="border px-2 py-1 align-top">${escapeHtml(c)}</td>`
        html += '</tr>'
        continue
      }
      // Fallback: treat as paragraph text if not a table
    } else if (tableHeader !== null) {
      // Table header collected but no separator; flush as text
      html += `<p class="my-2">${escapeHtml(tableHeader.join(' | '))}</p>`
      tableHeader = null
    }

    if (!pOpen) {
      closeList(); closeTable()
      html += '<p class="my-2">'
      pOpen = true
    }
    // Inline code and links (+ optional search highlight)
    const escaped = escapeHtml(line)
    const withCode = escaped.replace(/`([^`]+)`/g, '<code class="px-1 py-0.5 rounded bg-gray-100 dark:bg-white/10 text-[90%]">$1</code>')
    let withLinks = withCode.replace(/\[([^\]]+)\]\(([^\)]+)\)/g, '<a class="underline" href="$2" target="_blank" rel="noreferrer noopener">$1</a>')
    try {
      const q = (searchTerm || '').trim()
      if (q.length >= 2) {
        const re = new RegExp(`(${escapeRegExp(q)})`, 'gi')
        withLinks = withLinks.replace(re, '<mark>$1</mark>')
      }
    } catch {}
    html += withLinks + ' '
  }

  closeList(); closeTable()
  closeParagraph()
  return html
}

type TocItem = { id: string; text: string; level: number }

export default function MarkdownViewer({ src, searchTerm }: { src: string; searchTerm?: string }) {
  const [html, setHtml] = useState<string>('Loading...')
  const [toc, setToc] = useState<TocItem[]>([])

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const res = await fetch(src, { cache: 'no-store' })
        const text = await res.text()
        if (!cancelled) {
          // Build TOC by scanning headings in the markdown
          const lines = text.replaceAll('\r\n', '\n').split('\n')
          const tocItems: TocItem[] = []
          let md = ''
          let inCode = false
          for (const raw of lines) {
            const line = raw.trimEnd()
            if (line.startsWith('```')) { inCode = !inCode; continue }
            if (inCode) continue
            const m = line.match(/^(#{1,6})\s+(.*)$/)
            if (m) {
              const level = m[1].length
              const text = m[2].trim()
              const id = text.toLowerCase().replace(/[^a-z0-9\s-]/g, '').replace(/\s+/g, '-').slice(0, 64)
              tocItems.push({ id, text, level })
              md += line + '\n'
              continue
            }
            md += line + '\n'
          }
          setToc(tocItems)
          setHtml(renderMarkdown(md, searchTerm))
        }
      } catch (e: any) {
        if (!cancelled) {
          const errorMsg = escapeHtml(String(e?.message || e))
          setHtml(`<p class="text-red-600">Failed to load documentation: ${errorMsg}</p>`)
        }
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [src, searchTerm])

  return (
    <div className="grid grid-cols-1 md:grid-cols-[1fr_240px] gap-6">
      <div className="markdown max-w-none">
        <div dangerouslySetInnerHTML={{ __html: html }} />
      </div>
      <aside className="hidden md:block sticky top-16 h-max border-l border-gray-200 dark:border-white/10 pl-4">
        <div className="text-xs uppercase tracking-wide text-gray-500 dark:text-white/50 mb-2">On this page</div>
        <nav className="space-y-1">
          {toc.map((t, i) => (
            <a key={i} href={`#${t.id}`} className={`block text-sm hover:underline ${t.level > 2 ? 'pl-3' : ''}`}>
              {t.text}
            </a>
          ))}
        </nav>
      </aside>
    </div>
  )
}
