import { useEffect, useState } from 'react'
import { deleteAllData, getSettings, resetSettings, saveSettings, type Settings } from '../api.ts'
import { useApp } from './AppContext.tsx'

type Field = {
  key: string
  label: string
  min: number
  max: number
  step?: number
  initial: number
  /** Sliders for ratios run 0–100; the backend stores 0–1. */
  ratio?: boolean
  display: (raw: number) => string
}

const degrees = (v: number) => Math.round(v) + ' degrees'
const seconds = (v: number) => Math.round(v) + ' seconds'
const ear = (v: number) => v.toFixed(2)

const POSTURE: Field[] = [
  { key: 'neck_thresh', label: 'Neck angle threshold', min: 5, max: 60, initial: 20, display: degrees },
  { key: 'torso_thresh', label: 'Torso lean threshold', min: 5, max: 60, initial: 15, display: degrees },
  { key: 'pitch_thresh', label: 'Head pitch threshold', min: 5, max: 60, initial: 25, display: degrees },
  { key: 'roll_thresh', label: 'Head roll threshold', min: 5, max: 60, initial: 25, display: degrees },
  { key: 'shrug_ratio', label: 'Shoulder shrug sensitivity', min: 50, max: 99, initial: 90, ratio: true, display: v => Math.round(v * 100) + '%' },
  { key: 'shrug_dur', label: 'Shrug sustain before alert', min: 1, max: 120, initial: 10, display: seconds },
  { key: 'side_dur', label: 'Hunching sustain before alert', min: 1, max: 180, initial: 30, display: seconds },
]

const EYE: Field[] = [
  { key: 'ear_thresh', label: 'Eye narrowing threshold (EAR)', min: 5, max: 40, initial: 22, ratio: true, display: ear },
  { key: 'blink_thresh', label: 'Blink detection threshold (EAR)', min: 5, max: 40, initial: 18, ratio: true, display: ear },
  { key: 'low_blink_rate', label: 'Minimum blink rate', min: 2, max: 40, initial: 15, display: v => Math.round(v) + ' per minute' },
  { key: 'min_blink_win', label: 'Blink rate calculation window', min: 2, max: 60, initial: 10, display: seconds },
  { key: 'ear_dur', label: 'Eye narrowing sustain before alert', min: 1, max: 120, initial: 10, display: seconds },
  { key: 'blink_dur', label: 'Low blink sustain before alert', min: 1, max: 120, initial: 10, display: seconds },
  { key: 'head_dur', label: 'Head tilt sustain before alert', min: 1, max: 120, initial: 10, display: seconds },
]

const COOLDOWN: Field = { key: 'cooldown', label: 'Notification cooldown', min: 5, max: 600, step: 5, initial: 60, display: seconds }

const FIELDS = [...POSTURE, ...EYE, COOLDOWN]
const toRaw = (f: Field, ui: number) => (f.ratio ? ui / 100 : ui)
const toUi = (f: Field, raw: number) => (f.ratio ? Math.round(raw * 100) : raw)

/** Slider positions, keyed by backend setting name. */
type UiValues = Record<string, number>

function applySettings(prev: UiValues, settings: Settings): UiValues {
  const next = { ...prev }
  for (const f of FIELDS) if (f.key in settings) next[f.key] = toUi(f, settings[f.key])
  return next
}

type SliderProps = { f: Field; value: number; onChange: (v: number) => void; last?: boolean }

function SliderRow({ f, value, onChange, last }: SliderProps) {
  const id = `slider-${f.key}`
  return (
    <div className="slider-row" style={last ? { marginBottom: 4 } : undefined}>
      <div className="sr-top"><label htmlFor={id}>{f.label}</label><b>{f.display(toRaw(f, value))}</b></div>
      <input type="range" id={id} min={f.min} max={f.max} step={f.step ?? 1} value={value} onChange={e => onChange(Number(e.target.value))} />
    </div>
  )
}

export default function SettingsTab({ active }: { active: boolean }) {
  const { showToast, dataChanged } = useApp()
  const [values, setValues] = useState<UiValues>(() => Object.fromEntries(FIELDS.map(f => [f.key, f.initial])))
  const [note, setNote] = useState('Loading current thresholds from the backend…')
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved'>('idle')
  const [deleting, setDeleting] = useState(false)
  const [theme, setTheme] = useState<'paper' | 'dusk'>('paper')

  useEffect(() => {
    if (!active) return
    let cancelled = false
    getSettings().then(settings => {
      if (cancelled) return
      setValues(v => applySettings(v, settings))
      setNote('These thresholds are live — changes apply to detection as soon as you save.')
    }, () => {
      if (!cancelled) setNote("Couldn't reach the BackTrack backend at 127.0.0.1:5050 — showing default values until it's connected.")
    })
    return () => { cancelled = true }
  }, [active])

  const slider = (f: Field, last?: boolean) => (
    <SliderRow key={f.key} f={f} last={last} value={values[f.key]} onChange={v => setValues({ ...values, [f.key]: v })} />
  )

  async function save() {
    setSaveState('saving')
    try {
      const payload = Object.fromEntries(FIELDS.map(f => [f.key, toRaw(f, values[f.key])]))
      setValues(applySettings(values, await saveSettings(payload)))
      setSaveState('saved')
      setNote('Saved — the backend is now using these thresholds.')
    } catch (err) {
      setSaveState('idle')
      showToast('Settings not saved', (err as Error).message)
      return
    }
    setTimeout(() => setSaveState('idle'), 2000)
  }

  async function reset() {
    try {
      setValues(applySettings(values, await resetSettings()))
      setNote('Thresholds reset to defaults and saved.')
    } catch {
      showToast('Reset failed', "Couldn't reach the BackTrack backend.")
    }
  }

  async function deleteEverything() {
    if (!window.confirm("This permanently deletes every recorded session and resets your thresholds to defaults. This can't be undone. Continue?")) return
    setDeleting(true)
    try {
      setValues(applySettings(values, await deleteAllData()))
      showToast('Data deleted', 'All sessions were removed and thresholds reset to defaults.')
      dataChanged()
    } catch (err) {
      showToast('Deletion failed', (err as Error).message)
    }
    setDeleting(false)
  }

  return (
    <section className={active ? 'panel active' : 'panel'}>
      <div className="preview-note">{note}</div>
      <div className="settings-grid">
        <div className="card r-a settings-card">
          <h3>Posture sensitivity</h3>
          <p className="sc-sub">Set how much forward lean, tilt, or shoulder rise triggers an alert.</p>
          {POSTURE.map((f, i) => slider(f, i === POSTURE.length - 1))}
        </div>

        <div className="card r-c settings-card">
          <h3>Eye strain sensitivity</h3>
          <p className="sc-sub">Set the eye narrowing and blink rate that count as strain.</p>
          {EYE.map((f, i) => slider(f, i === EYE.length - 1))}
        </div>

        <div className="card r-b settings-card">
          <h3>Notifications</h3>
          <p className="sc-sub">Choose how often BackTrack can repeat the same alert.</p>
          {slider(COOLDOWN, true)}
          <p className="sc-sub" style={{ margin: '14px 0 0' }}>Reminder frequency and quiet hours below are local display preferences and aren't yet read by the backend.</p>
          <div className="select-row" style={{ marginTop: 10 }}>
            <label htmlFor="reminderFreq">Reminder frequency</label>
            <select id="reminderFreq" defaultValue="Every 20 minutes">
              <option>Every 10 minutes</option><option>Every 20 minutes</option><option>Every 30 minutes</option><option>Only on threshold breach</option>
            </select>
          </div>
          <div className="select-row" style={{ marginBottom: 0 }}>
            <label htmlFor="quietHours">Quiet hours</label>
            <select id="quietHours" defaultValue="7:00 PM to 8:00 AM">
              <option>None</option><option>7:00 PM to 8:00 AM</option><option>Custom range</option>
            </select>
          </div>
        </div>

        <div className="card r-a settings-card">
          <h3>Appearance</h3>
          <p className="sc-sub">Pick the display theme for the whole app.</p>
          <div className="theme-options">
            <div className={theme === 'paper' ? 'theme-opt selected' : 'theme-opt'} onClick={() => setTheme('paper')}><div className="swatch paper"></div><span>Rice Paper</span></div>
            <div className={theme === 'dusk' ? 'theme-opt selected' : 'theme-opt'} onClick={() => setTheme('dusk')}><div className="swatch dusk"></div><span>Loam Dusk</span></div>
          </div>
        </div>

        <div className="card r-c settings-card danger-card">
          <h3>Danger zone</h3>
          <p className="sc-sub">Permanently erase every session and reset all thresholds for this account. This can't be undone.</p>
          <button className="danger-btn" disabled={deleting} onClick={deleteEverything}>{deleting ? 'Deleting…' : 'Delete all my data'}</button>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
        <button className="save-btn" disabled={saveState !== 'idle'} onClick={save}>
          {saveState === 'saving' ? 'Saving…' : saveState === 'saved' ? 'Preferences saved' : 'Save preferences'}
        </button>
        <button type="button" className="link-btn" onClick={reset}>Reset thresholds to defaults</button>
      </div>
    </section>
  )
}
