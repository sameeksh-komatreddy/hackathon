import { useEffect, useState } from 'react'
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

export default function App() {
  const [signedIn, setSignedIn] = useState(false)
  const [tab, setTab] = useState<Tab>('history')
  const [title, sub] = TAB_TITLES[tab]

  return (
    <>
      <div className="ambient-blob blob-a"></div>
      <div className="ambient-blob blob-b"></div>
      <div className="ambient-blob blob-c"></div>
      <div className="grain"></div>

      <div id="app">
        {!signedIn ? (
          <LoginScreen onSignIn={() => setSignedIn(true)} />
        ) : (
          <div id="app-shell">
            <Sidebar
              active={tab}
              onSelect={setTab}
              onSignOut={() => {
                setSignedIn(false)
                setTab('history')
              }}
            />
            <main className="main">
              <div className="topbar">
                <div>
                  <div className="topbar-title">{title}</div>
                  <div className="topbar-sub">{sub}</div>
                </div>
                <div className="topbar-right">
                  <Clock />
                  <div className="avatar">JR</div>
                </div>
              </div>

              <HistoryTab active={tab === 'history'} />
              <RecordTab active={tab === 'record'} />
              <ExportTab active={tab === 'export'} />
              <SettingsTab active={tab === 'settings'} />
            </main>
          </div>
        )}
      </div>

      <Toast show={false} title="Posture threshold reached" body="You've been leaning forward for 45 seconds. Try straightening up." onClose={() => {}} />
    </>
  )
}
