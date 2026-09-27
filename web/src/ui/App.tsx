import { useCallback, useEffect, useMemo, useState } from 'react'
import * as api from '../api.ts'
import { AppContext, type AppState } from './AppContext.tsx'
import LoginScreen from './LoginScreen.tsx'
import Sidebar from './Sidebar.tsx'
import Toast from './Toast.tsx'
import HistoryTab from './HistoryTab.tsx'
import RecordTab from './RecordTab.tsx'
import ExportTab from './ExportTab.tsx'
import SettingsTab from './SettingsTab.tsx'
import { TAB_TITLES, type Tab } from './tabs.ts'

function Clock() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])
  return (
    <div className="clock">
      <span className="dot-pulse"></span>
      <span>{now.toLocaleTimeString('en-US', { hour12: false })}</span>
    </div>
  )
}

function initialsFor(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return '?'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

type ToastState = { show: boolean; title: string; body: string; id: number }

export default function App() {
  const [user, setUser] = useState<api.User | null>(null)
  // Only show the login screen once we know a saved login can't be resumed.
  const [resuming, setResuming] = useState(api.hasToken)
  const [tab, setTab] = useState<Tab>('history')
  const [latestScore, setLatestScore] = useState<number | null>(null)
  const [dataVersion, setDataVersion] = useState(0)
  const [toast, setToast] = useState<ToastState>({ show: false, title: '', body: '', id: 0 })

  useEffect(() => {
    if (!api.hasToken()) return
    api.resumeSession().then(u => {
      setUser(u)
      setResuming(false)
    })
  }, [])

  // Each new toast restarts the 6 second auto-hide.
  useEffect(() => {
    if (!toast.show) return
    const id = setTimeout(() => setToast(t => ({ ...t, show: false })), 6000)
    return () => clearTimeout(id)
  }, [toast.show, toast.id])

  const showToast = useCallback((title: string, body: string) => {
    setToast(t => ({ show: true, title, body, id: t.id + 1 }))
  }, [])

  const dataChanged = useCallback(() => setDataVersion(v => v + 1), [])

  const ctx = useMemo<AppState | null>(
    () => (user ? { user, showToast, dataVersion, dataChanged } : null),
    [user, showToast, dataVersion, dataChanged],
  )

  async function signOut() {
    // Stop a running session first; once the token is gone it can't be stopped.
    try {
      if ((await api.recordingStatus()).recording) await api.stopRecording()
    } catch { /* offline: nothing to stop */ }
    await api.signOut()
    setUser(null)
    setTab('history')
    setLatestScore(null)
  }

  const [title, sub] = TAB_TITLES[tab]

  return (
    <>
      <div className="ambient-blob blob-a"></div>
      <div className="ambient-blob blob-b"></div>
      <div className="ambient-blob blob-c"></div>
      <div className="grain"></div>

      <div id="app">
        {resuming ? null : !ctx ? (
          <LoginScreen onSignIn={setUser} />
        ) : (
          <AppContext.Provider value={ctx}>
            <div id="app-shell">
              <Sidebar active={tab} onSelect={setTab} onSignOut={signOut} latestScore={latestScore} />
              <main className="main">
                <div className="topbar">
                  <div>
                    <div className="topbar-title">{title}</div>
                    <div className="topbar-sub">{sub}</div>
                  </div>
                  <div className="topbar-right">
                    <Clock />
                    <div className="avatar">{initialsFor(ctx.user.name)}</div>
                  </div>
                </div>

                <HistoryTab active={tab === 'history'} onLatestScore={setLatestScore} />
                <RecordTab active={tab === 'record'} />
                <ExportTab active={tab === 'export'} />
                <SettingsTab active={tab === 'settings'} />
              </main>
            </div>
          </AppContext.Provider>
        )}
      </div>

      <Toast show={toast.show} title={toast.title} body={toast.body} onClose={() => setToast(t => ({ ...t, show: false }))} />
    </>
  )
}
