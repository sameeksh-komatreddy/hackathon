import type { ReactNode } from 'react'
import SpineLogo from './SpineLogo.tsx'
import { TABS, TAB_TITLES, type Tab } from './tabs.ts'

const ICONS: Record<Tab, ReactNode> = {
  history: <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M3 3v18h18" /><path d="M7 15l4-6 4 3 5-8" /></svg>,
  record: <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="8" /><circle cx="12" cy="12" r="3" fill="currentColor" stroke="none" /></svg>,
  export: <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M12 3v12" /><path d="M7 10l5 5 5-5" /><path d="M4 19h16" /></svg>,
  settings: <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 00.3 1.9l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.7 1.7 0 00-1.9-.3 1.7 1.7 0 00-1 1.6V21a2 2 0 11-4 0v-.1a1.7 1.7 0 00-1-1.6 1.7 1.7 0 00-1.9.3l-.1.1a2 2 0 112.8-2.8l.1-.1a1.7 1.7 0 00.3-1.9 1.7 1.7 0 00-1.6-1H3a2 2 0 110-4h.1a1.7 1.7 0 001.6-1 1.7 1.7 0 00-.3-1.9l-.1-.1a2 2 0 112.8 2.8l-.1.1a1.7 1.7 0 00-.3 1.9V9a1.7 1.7 0 001.6 1H21a2 2 0 110 4h-.1a1.7 1.7 0 00-1.6 1z" /></svg>,
}

type Props = {
  active: Tab
  onSelect: (tab: Tab) => void
  onSignOut: () => void
  latestScore: number | null
}

export default function Sidebar({ active, onSelect, onSignOut, latestScore }: Props) {
  return (
    <aside className="sidebar">
      <div className="brand-mark">
        <div className="spine-logo-wrap" style={{ width: 38, height: 38 }}>
          <SpineLogo width={19} height={22} />
        </div>
        <div className="wordmark" style={{ fontSize: 17 }}>BackTrack</div>
      </div>

      <div className="nav-group-label">Workspace</div>
      <ul className="nav-list">
        {TABS.map(tab => (
          <li key={tab}>
            <button
              className={tab === active ? 'nav-item active' : 'nav-item'}
              aria-current={tab === active ? 'page' : undefined}
              onClick={() => onSelect(tab)}
            >
              {ICONS[tab]}
              {TAB_TITLES[tab][0]}
              {tab === 'record' && <span className="tick"></span>}
            </button>
          </li>
        ))}
      </ul>

      <div className="sidebar-foot">
        <div className="session-mini">
          <div className="label">Latest session score</div>
          <div className="value">
            <span>{latestScore ?? '--'}</span>{' '}
            <span style={{ fontSize: 12, color: 'var(--muted-fg)', fontWeight: 600, fontFamily: 'var(--font-body)' }}>out of 100</span>
          </div>
        </div>
        <button className="logout-btn" onClick={onSignOut}>Sign out</button>
      </div>
    </aside>
  )
}
