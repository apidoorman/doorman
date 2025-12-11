'use client'

import { useSearchParams } from 'next/navigation'
import AnalyticsPageContent from './AnalyticsPageContent'

export default function AnalyticsContent() {
  const searchParams = useSearchParams()
  return <AnalyticsPageContent searchParams={searchParams} />
}
