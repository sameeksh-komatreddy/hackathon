import { useEffect, useState } from 'react'
import { exportPdf, getSessions, type Session } from '../api.ts'
import { useApp } from './AppContext.tsx'
import { average } from './history.ts'

const CHECKS = [
  { key: 'posture', title: 'Posture data', desc: 'Session scores, angle readings, and drift patterns' },
  { key: 'eye', title: 'Eye strain data', desc: 'Blink rate and strain index history' },
  { key: 'trend', title: 'Trend summary', desc: 'Session over session changes and automated insights' },
  { key: 'sessions', title: 'Session log', desc: 'Full list of individual sessions with duration and averages' },
]

const DOWNLOAD_ICON = <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 3v12" /><path d="M7 10l5 5 5-5" /><path d="M4 19h16" /></svg>
const CHECK_ICON = <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 6L9 17l-5-5" /></svg>

/** YYYY-MM-DD in local time (toISOString would give the UTC date). */
function isoLocal(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function fmtDateLong(iso: string) {
  const d = new Date(iso + 'T00:00:00')
  if (isNaN(d.getTime())) return iso
  return d.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
}

export default function ExportTab({ active }: { active: boolean }) {
  const { user, showToast } = useApp()
  const [sections, setSections] = useState<Record<string, boolean>>({ posture: true, eye: true, trend: false, sessions: false })
  const [from, setFrom] = useState(() => { const d = new Date(); d.setDate(d.getDate() - 30); return isoLocal(d) })
  const [to, setTo] = useState(() => isoLocal(new Date()))
  const [sessions, setSessions] = useState<Session[] | null>(null)
  const [offline, setOffline] = useState(false)
  const [pdfState, setPdfState] = useState<'idle' | 'working' | 'done'>('idle')

  useEffect(() => {
    if (!active) return
    let cancelled = false
    getSessions(0).then(
      all => { if (!cancelled) { setSessions(all); setOffline(false) } },
      () => { if (!cancelled) setOffline(true) },
    )
    return () => { cancelled = true }
  }, [active, from, to])

  const inRange = (sessions ?? []).filter(s => {
    const d = (s.start_time || '').slice(0, 10)
    return d && !(from && d < from) && !(to && d > to)
  })
  // A session can have a posture score without an eye score (or vice versa)
  // when only one camera was in use, so average each over its own sessions.
  const postureAvg = average(inRange.map(s => s.posture_score).filter((v): v is number => v != null))
  const eyeAvg = average(inRange.map(s => s.eye_strain_index).filter((v): v is number => v != null))

  const note = offline ? "Couldn't reach the BackTrack backend — connect it to preview and generate reports."
    : !sessions ? 'Pulling your session history from the backend…'
    : inRange.length === 0 ? 'No sessions fall in this date range yet — widen the range or record a session first.'
    : `${inRange.length} session${inRange.length === 1 ? '' : 's'} found in this range, ready to export.`

  const anyChecked = Object.values(sections).some(Boolean)

  async function generate() {
    setPdfState('working')
    try {
      const blob = await exportPdf({ sections, from, to, patient_name: user.name })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'backtrack-report.pdf'
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
      setPdfState('done')
      setTimeout(() => setPdfState('idle'), 2200)
    } catch (err) {
      setPdfState('idle')
      showToast('Export failed', (err as Error).message)
    }
  }

  return (
    <section className={active ? 'panel active' : 'panel'}>
      <div className="preview-note">{note}</div>
      <div className="export-layout">
        <div>
          <div className="section-head" style={{ marginTop: 0 }}><h2>Include in report</h2></div>
          <ul className="check-list">
            {CHECKS.map(c => (
              <li className="check-item" key={c.key}>
                <input type="checkbox" id={`chk-${c.key}`} checked={sections[c.key]}
                  onChange={e => setSections({ ...sections, [c.key]: e.target.checked })} />
                <label className="ci-text" htmlFor={`chk-${c.key}`}><b>{c.title}</b><span>{c.desc}</span></label>
              </li>
            ))}
          </ul>

          <div className="range-row">
            <div className="field"><label htmlFor="exportFrom">From</label><input type="date" id="exportFrom" value={from} onChange={e => setFrom(e.target.value)} /></div>
            <div className="field"><label htmlFor="exportTo">To</label><input type="date" id="exportTo" value={to} onChange={e => setTo(e.target.value)} /></div>
          </div>

          <button className="pdf-btn" disabled={!anyChecked || pdfState !== 'idle'} onClick={generate}>
            {pdfState === 'working' ? 'Generating report…'
              : pdfState === 'done' ? <>{CHECK_ICON} Report downloaded</>
              : <>{DOWNLOAD_ICON} Generate PDF report</>}
          </button>
          <p className="rec-note">Built to hand to a physical therapist or doctor: plain figures, no jargon, one section per category.</p>
        </div>

        <div className="card r-b report-preview">
          <div className="report-sheet">
            <div className="rs-head"><b>BackTrack Report</b><span>{new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}</span></div>
            <div className="rs-row"><span>Patient</span><b>{user.name}</b></div>
            <div className="rs-row"><span>Range</span><b>{(from ? fmtDateLong(from) : 'earliest') + ' to ' + (to ? fmtDateLong(to) : 'latest')}</b></div>
            <div className="rs-row"><span>Average posture score</span><b>{postureAvg != null ? Math.round(postureAvg) + ' out of 100' : '--'}</b></div>
            <div className="rs-row"><span>Average eye strain index</span><b>{eyeAvg != null ? eyeAvg.toFixed(1) + ' out of 10' : '--'}</b></div>
            <div className="rs-block"></div>
            <div className="rs-row"><span>Sessions included</span><b>{inRange.length}</b></div>
            <div className="rs-row" style={{ borderBottom: 'none' }}><span>Format</span><b>PDF</b></div>
          </div>
        </div>
      </div>
    </section>
  )
}
