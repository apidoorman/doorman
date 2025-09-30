'use client'

export default function PublicPage() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-4">Public Page</h1>
      <p>This page doesn't require authentication.</p>
      <p>If you can see this, routing is working correctly.</p>
    </div>
  )
}