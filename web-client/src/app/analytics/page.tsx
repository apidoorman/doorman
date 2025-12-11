import { Suspense } from 'react'
import AnalyticsContent from './AnalyticsContent'

export default function AnalyticsPage() {
  return (
    <Suspense fallback={<div className="p-6">Loading analytics...</div>}>
      <AnalyticsContent />
    </Suspense>
  )
}
