'use client'

import Link from 'next/link'
import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from 'react'

type Tone = 'ink' | 'white' | 'lime' | 'terracotta' | 'blue' | 'dark'
type Status = 'healthy' | 'attention' | 'info' | 'critical' | 'neutral'

export function SignalPageHeader({ kicker, title, description, actions, className = '' }: { kicker: string; title: ReactNode; description?: ReactNode; actions?: ReactNode; className?: string }) {
  return <header className={`signal-page-header ${className}`}><div><p className="signal-kicker">{kicker}</p><h1 className="signal-page-title">{title}</h1>{description && <p className="signal-page-description">{description}</p>}</div>{actions && <div className="signal-page-actions">{actions}</div>}</header>
}

export function SignalPanel({ children, tone = 'white', title, kicker, className = '', ...props }: HTMLAttributes<HTMLElement> & { tone?: Tone; title?: ReactNode; kicker?: ReactNode }) {
  return <section className={`signal-panel signal-panel--${tone} ${className}`} {...props}>{(title || kicker) && <header className="signal-panel__header"><div>{kicker && <p className="signal-kicker">{kicker}</p>}{title && <h2>{title}</h2>}</div></header>}<div className="signal-panel__body">{children}</div></section>
}

export function SignalMetric({ label, value, detail, tone = 'white' }: { label: ReactNode; value: ReactNode; detail?: ReactNode; tone?: Tone }) { return <div className={`signal-metric signal-metric--${tone}`}><p>{label}</p><strong>{value}</strong>{detail && <span>{detail}</span>}</div> }
export type SignalRecordIconKind = 'user' | 'group' | 'role' | 'routing'

export function SignalRecordIcon({ kind, className = '' }: { kind: SignalRecordIconKind; className?: string }) {
  const artwork: Record<SignalRecordIconKind, ReactNode> = {
    user: <><circle cx="12" cy="8" r="3" /><path d="M5 20c.6-3.4 2.9-5 7-5s6.4 1.6 7 5" /></>,
    group: <><circle cx="8" cy="9" r="2.5" /><circle cx="16" cy="9" r="2.5" /><path d="M3.5 20c.4-3 2.1-4.5 4.5-4.5M16 15.5c2.4 0 4.1 1.5 4.5 4.5M7 18c.5-2.8 2.1-4.2 5-4.2s4.5 1.4 5 4.2" /></>,
    role: <><path d="M12 3 19 6v5c0 4.4-2.8 7.7-7 10-4.2-2.3-7-5.6-7-10V6l7-3Z" /><path d="m9 12 2 2 4-4" /></>,
    routing: <><path d="M4 7h10" /><path d="m11 4 3 3-3 3" /><path d="M20 17H10" /><path d="m13 14-3 3 3 3" /></>,
  }
  return <span className={`signal-record-icon signal-record-icon--${kind} ${className}`} aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{artwork[kind]}</svg></span>
}

export function SignalStatusTag({ children, status = 'neutral' }: { children: ReactNode; status?: Status }) { return <span className={`signal-status signal-status--${status}`}>{children}</span> }
export function SignalTable({ className = '', children, ...props }: HTMLAttributes<HTMLTableElement>) { return <div className="signal-table-wrap"><table className={`signal-table ${className}`} {...props}>{children}</table></div> }
export function SignalFormSection({ number, title, description, children, className = '' }: { number: string; title: ReactNode; description?: ReactNode; children: ReactNode; className?: string }) { return <section className={`signal-form-section ${className}`}><header><span>{number}</span><div><h2>{title}</h2>{description && <p>{description}</p>}</div></header><div className="signal-form-section__body">{children}</div></section> }
export function SignalEmptyState({ title, children, action }: { title: ReactNode; children?: ReactNode; action?: ReactNode }) { return <div className="signal-empty"><p className="signal-kicker">NO RECORDS</p><h2>{title}</h2>{children && <p>{children}</p>}{action && <div>{action}</div>}</div> }
export function SignalSidebarRail({ title = 'OPERATIONS', children, className = '' }: { title?: ReactNode; children: ReactNode; className?: string }) { return <aside className={`signal-sidebar-rail ${className}`}><p className="signal-kicker">{title}</p>{children}</aside> }
export function SignalPrimaryButton({ className = '', children, ...props }: ButtonHTMLAttributes<HTMLButtonElement>) { return <button className={`signal-button signal-button--primary ${className}`} {...props}>{children}</button> }
export function SignalDangerButton({ className = '', children, ...props }: ButtonHTMLAttributes<HTMLButtonElement>) { return <button className={`signal-button signal-button--danger ${className}`} {...props}>{children}</button> }
export function SignalPrimaryLink({ href, className = '', children }: { href: string; className?: string; children: ReactNode }) { return <Link href={href} className={`signal-button signal-button--primary ${className}`}>{children}</Link> }

export function AppShell({ children }: { children: ReactNode }) {
  return <div className="signal-app-shell">{children}</div>
}
