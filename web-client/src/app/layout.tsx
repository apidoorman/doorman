import type { Metadata } from 'next'
import './globals.css'
import { AuthProvider } from '@/contexts/AuthContext'
import { ToastProvider } from '@/contexts/ToastContext'

export const metadata: Metadata = {
  title: 'Doorman — API + AI Gateway',
  description: 'Doorman operational API gateway control plane',
  icons: { icon: [{ url: '/doorman-mark.svg?v=doorman-site', type: 'image/svg+xml' }], apple: [{ url: '/apple-touch-icon.png?v=doorman-site', sizes: '180x180', type: 'image/png' }] },
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en" className="h-full"><head><link rel="preconnect" href="https://fonts.googleapis.com" /><link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" /><link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet" /></head><body className="h-full transition-colors duration-200"><AuthProvider><ToastProvider>{children}</ToastProvider></AuthProvider></body></html>
}
