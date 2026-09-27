import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import {
  feedUrl, openStream, recalibrate, recordingStatus, sendTestNotification, startRecording, stopRecording,
  type CameraRole, type StreamData,
} from '../api.ts'
import { useApp } from './AppContext.tsx'
import CameraSetup from './CameraSetup.tsx'

const THRESHOLD_BARS = [
  { label: 'Eye narrowing', secsKey: 'low_ear_secs', durKey: 'ear_dur' },
  { label: 'Head tilt', secsKey: 'head_secs', durKey: 'head_dur' },
  { label: 'Blink rate', secsKey: 'blink_low_secs', durKey: 'blink_dur' },
  { label: 'Shoulder shrug', secsKey: 'shrug_secs', durKey: 'shrug_dur' },
  { label: 'Hunching', secsKey: 'bad_side_secs', durKey: 'side_dur' },
]
const DEFAULT_HINT = 'Each bar fills as that specific issue is sustained. When one is full, a notification fires natively on your device — on screen over anything else you have open — not just inside this page.'
const FIRED_HINT = 'Threshold reached — a native notification just fired on your device.'
const IDLE_NOTE = 'Press Start recording to connect to the BackTrack backend at 127.0.0.1:5050.'
const RECORDING_NOTE = 'Connected to the BackTrack backend. Recording in progress.'

function fmt(s: number) {
  const hh = String(Math.floor(s / 3600)).padStart(2, '0')
  const mm = String(Math.floor((s % 3600) / 60)).padStart(2, '0')
  return `${hh}:${mm}:${String(s % 60).padStart(2, '0')}`
}
function fmtShort(s: number) {
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
}
const degrees = (v: number | undefined) => (v || 0).toFixed(1) + ' degrees'

function CamStatus({ online }: { online: boolean }) {
  return <span className={online ? 'cam-status' : 'cam-status offline'}><span className="dot"></span>{online ? 'Tracking you' : 'Not tracking'}</span>
}

/** MJPEG feed with a placeholder until the first frame arrives. Remount (key) to reconnect. */
function Feed({ src, name }: { src: string | null; name: string }) {
  const [loaded, setLoaded] = useState(false)
  return (
    <div className="cam-view">
      <img className={src && loaded ? 'cam-feed-img' : 'cam-feed-img hidden'} alt={`${name} feed`}
        src={src ?? undefined} onLoad={() => setLoaded(true)} onError={() => setLoaded(false)} />
      <div className={src && loaded ? 'cam-placeholder hidden' : 'cam-placeholder'}>
        <span className="dot-pulse offline"></span>
        <span>Connecting to the {name.toLowerCase()}…</span>
      </div>
    </div>
  )
}

type CamProps = {
  cardClass: string
  role: CameraRole
  name: string
  icon: ReactNode
  online: boolean
  feed: string | null
  feet: [string, string][]
}

function CamPanel({ cardClass, role, name, icon, online, feed, feet }: CamProps) {
  const [recalibrating, setRecalibrating] = useState(false)

  async function recal() {
    setRecalibrating(true)
    try {
      await recalibrate(role)
    } catch (err) {
      console.warn('The recalibration request may still have reached the backend even though the response could not be read here.', err)
    }
    setTimeout(() => setRecalibrating(false), 1500)
  }

  return (
    <div className={`card ${cardClass} cam-panel`}>
      <div className="cam-head">
        <span className="cam-name">{icon} {name}</span>
        <CamStatus online={online} />
        <button className="recal-btn" disabled={recalibrating} onClick={recal}>{recalibrating ? 'Recalibrating' : 'Recalibrate'}</button>
      </div>
      <Feed key={feed ?? 'off'} src={feed} name={name} />
      <div className="cam-foot">{feet.map(([label, val]) => <span key={label}>{label} <b>{val}</b></span>)}</div>
    </div>
  )
}

function ThresholdBar({ label, progress, onFired }: { label: string; progress: number; onFired: () => void }) {
  const prev = useRef(progress)
  const [fires, setFires] = useState(0)
  useEffect(() => {
    if (prev.current < 1 && progress >= 1) {
      setFires(n => n + 1)
      onFired()
    }
    prev.current = progress
  }, [progress, onFired])

  const pct = Math.round(progress * 100)
  const cls = ['threshold-fill', pct >= 70 && 'hot', fires > 0 && 'fired'].filter(Boolean).join(' ')
  return (
    <div className="threshold-item">
      <div className="threshold-item-top"><span className="threshold-item-label">{label}</span><span className="threshold-item-pct">{pct}%</span></div>
      {/* keyed on the fire count so the flash animation restarts each time */}
      <div className="threshold-track"><div key={fires} className={cls} style={{ width: pct + '%' }}></div></div>
    </div>
  )
}

export default function RecordTab({ active }: { active: boolean }) {
  const { showToast, dataChanged } = useApp()
  const [recording, setRecording] = useState(false)
  const [startMs, setStartMs] = useState(0)
  const [now, setNow] = useState(() => Date.now())
  const [finalElapsed, setFinalElapsed] = useState(0)
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState(IDLE_NOTE)
  const [live, setLive] = useState<StreamData | null>(null)
  const [hintFired, setHintFired] = useState(false)
  const [testing, setTesting] = useState(false)
  const hintTimer = useRef<ReturnType<typeof setTimeout>>(undefined)
  const lastAlerts = useRef('')
  const stream = useRef<EventSource | null>(null)

  // Pick up a session that was already recording (e.g. after a page reload).
  useEffect(() => {
    recordingStatus().then(s => {
      if (!s.recording) return
      setStartMs(s.startMs ?? Date.now())
      setRecording(true)
      setNote(RECORDING_NOTE)
    }, () => {})
  }, [])

  // Elapsed-time clock while recording.
  useEffect(() => {
    if (!recording) return
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [recording])

  // Live stream from the backend while recording.
  useEffect(() => {
    if (!recording) return
    const es = openStream()
    stream.current = es
    es.onmessage = e => {
      let data: StreamData
      try { data = JSON.parse(e.data) } catch { return }
      setLive(data)
      const alerts = Array.isArray(data.alerts) ? data.alerts : []
      const key = alerts.join('|')
      // The backend sends the native OS notification itself; this toast is
      // just an in-page echo for while you're looking at the tab.
      if (alerts.length && key !== lastAlerts.current) showToast('Alert from BackTrack', alerts[0])
      lastAlerts.current = key
    }
    es.onerror = () => {
      setLive(null)
      setNote('Lost connection to the BackTrack backend. Reconnecting…')
    }
    es.onopen = () => setNote(RECORDING_NOTE)
    return () => {
      es.close()
      setLive(null)
      lastAlerts.current = ''
    }
  }, [recording, showToast])

  useEffect(() => () => clearTimeout(hintTimer.current), [])

  // Previews run whenever the Record tab is open (not only while recording)
  // so you can check which camera is which before you start.
  const feedsShown = active || recording
  const feeds = useMemo(
    () => (feedsShown ? { front: feedUrl('front'), side: feedUrl('side') } : null),
    [feedsShown],
  )

  const fired = useMemo(() => () => {
    setHintFired(true)
    clearTimeout(hintTimer.current)
    hintTimer.current = setTimeout(() => setHintFired(false), 4000)
  }, [])

  async function toggleRecording() {
    setBusy(true)
    if (!recording) {
      try {
        await startRecording()
        setStartMs(Date.now())
        setRecording(true)
        setNote(RECORDING_NOTE)
      } catch {
        setNote("Couldn't reach the BackTrack backend at 127.0.0.1:5050. Start it and try again.")
      }
    } else {
      try {
        // Close the stream first so a late alert can't replace the "Session saved" toast.
        stream.current?.close()
        const summary = await stopRecording()
        setNote('Session saved. Press Start recording to begin a new session.')
        if (summary) {
          const score = summary.posture_score != null ? Math.round(summary.posture_score) : '--'
          showToast('Session saved', `Posture score ${score} out of 100 — added to your history.`)
        }
      } catch {
        setNote('Recording stopped, but the session may not have been saved — check the backend connection.')
      }
      setFinalElapsed(Math.max(0, Math.floor((Date.now() - startMs) / 1000)))
      setRecording(false)
      dataChanged()
    }
    setBusy(false)
  }

  async function testNotification() {
    setTesting(true)
    try {
      await sendTestNotification()
      showToast('Test sent', "Check your device's notification area. If nothing appeared, check the backend console for a permissions hint.")
    } catch (err) {
      showToast('Test failed', (err as Error).message)
    }
    setTimeout(() => setTesting(false), 1200)
  }

  // After stopping, the timer keeps showing the finished session's length.
  const elapsed = recording ? Math.max(0, Math.floor((now - startMs) / 1000)) : finalElapsed
  const neck = live?.neck_angle || 0
  const blink = live?.blink_rate || 0

  return (
    <section className={active ? 'panel active' : 'panel'}>
      <div className="preview-note">{note}</div>

      <CameraSetup active={active} />

      <div className="rec-grid">
        <CamPanel
          cardClass="r-a" role="front" name="Front camera" online={!!live?.calibrated_front} feed={feeds?.front ?? null}
          icon={<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2" y="6" width="14" height="12" rx="2" /><path d="M16 10l6-4v12l-6-4" /></svg>}
          feet={[['Head pitch', degrees(Math.abs(live?.pitch || 0))], ['Head roll', degrees(Math.abs(live?.roll || 0))]]}
        />
        <CamPanel
          cardClass="r-c" role="side" name="Side camera" online={!!live?.calibrated_side} feed={feeds?.side ?? null}
          icon={<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="7" y="2" width="10" height="20" rx="2" /><line x1="11" y1="18" x2="13" y2="18" /></svg>}
          feet={[['Neck angle', degrees(live?.neck_angle)], ['Torso lean', degrees(live?.torso_angle)]]}
        />
      </div>

      <div className="rec-controls">
        <button className={recording ? 'record-btn recording' : 'record-btn'} disabled={busy} onClick={toggleRecording}>
          <span className="rec-dot"></span><span>{recording ? 'Stop recording' : 'Start recording'}</span>
        </button>
        <span className="rec-timer">{fmt(elapsed)}</span>
      </div>
      <p className="rec-note">Notifications will alert you when posture or eye strain thresholds are crossed, both as pop-ups here and as system notifications on your device, for as long as a session is recording — even if another window is focused.</p>

      <div className="card r-b threshold-panel">
        <div className="threshold-panel-head">
          <span className="threshold-panel-title">Notification thresholds</span>
          <button className="threshold-test-btn" type="button" disabled={testing} onClick={testNotification}>{testing ? 'Sending…' : 'Send test notification'}</button>
        </div>
        <div className="threshold-grid">
          {THRESHOLD_BARS.map(bar => {
            const secs = Number(live?.[bar.secsKey]) || 0
            const dur = live?.durations?.[bar.durKey] || 1
            return <ThresholdBar key={bar.label} label={bar.label} progress={Math.max(0, Math.min(1, secs / dur))} onFired={fired} />
          })}
        </div>
        <p className="threshold-hint">{hintFired ? FIRED_HINT : DEFAULT_HINT}</p>
      </div>

      <div className="section-head"><h2>Live readout</h2><span className="hint">Updating from the backend stream</span></div>
      <div className="live-metrics">
        <div className="card r-a live-metric">
          <div className="lm-label">Neck angle</div><div className="lm-val">{degrees(neck)}</div>
          <div className="bar-track"><div className="bar-fill" style={{ width: Math.min(100, (neck / 40) * 100) + '%' }}></div></div>
        </div>
        <div className="card r-b live-metric">
          <div className="lm-label">Blink rate</div>
          <div className="lm-val">{Math.round(blink)}<span style={{ fontSize: 13, color: 'var(--muted-fg)', fontFamily: 'var(--font-body)' }}> per minute</span></div>
          <div className="bar-track"><div className="bar-fill" style={{ width: Math.min(100, (blink / 30) * 100) + '%', background: 'linear-gradient(90deg,var(--destructive),var(--secondary))' }}></div></div>
        </div>
        <div className="card r-c live-metric">
          <div className="lm-label">Elapsed</div><div className="lm-val">{fmtShort(elapsed)}</div>
          <div className="bar-track"><div className="bar-fill" style={{ width: Math.min(100, (elapsed / 1800) * 100) + '%' }}></div></div>
        </div>
      </div>
    </section>
  )
}
