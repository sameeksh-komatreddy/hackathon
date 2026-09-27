import { useState } from 'react'

type Slider = {
  key: string
  label: string
  min: number
  max: number
  step?: number
  initial: number
  format: (v: number) => string
}

const degrees = (v: number) => `${v} degrees`
const seconds = (v: number) => `${v} seconds`
const ear = (v: number) => (v / 100).toFixed(2)

const POSTURE: Slider[] = [
  { key: 'NeckThresh', label: 'Neck angle threshold', min: 5, max: 60, initial: 20, format: degrees },
  { key: 'TorsoThresh', label: 'Torso lean threshold', min: 5, max: 60, initial: 15, format: degrees },
  { key: 'PitchThresh', label: 'Head pitch threshold', min: 5, max: 60, initial: 25, format: degrees },
  { key: 'RollThresh', label: 'Head roll threshold', min: 5, max: 60, initial: 25, format: degrees },
  { key: 'ShrugRatio', label: 'Shoulder shrug sensitivity', min: 50, max: 99, initial: 90, format: v => `${v}%` },
  { key: 'ShrugDur', label: 'Shrug sustain before alert', min: 1, max: 120, initial: 10, format: seconds },
  { key: 'SideDur', label: 'Hunching sustain before alert', min: 1, max: 180, initial: 30, format: seconds },
]

const EYE: Slider[] = [
  { key: 'EarThresh', label: 'Eye narrowing threshold (EAR)', min: 5, max: 40, initial: 22, format: ear },
  { key: 'BlinkThresh', label: 'Blink detection threshold (EAR)', min: 5, max: 40, initial: 18, format: ear },
  { key: 'LowBlinkRate', label: 'Minimum blink rate', min: 2, max: 40, initial: 15, format: v => `${v} per minute` },
  { key: 'MinBlinkWin', label: 'Blink rate calculation window', min: 2, max: 60, initial: 10, format: seconds },
  { key: 'EarDur', label: 'Eye narrowing sustain before alert', min: 1, max: 120, initial: 10, format: seconds },
  { key: 'BlinkDur', label: 'Low blink sustain before alert', min: 1, max: 120, initial: 10, format: seconds },
  { key: 'HeadDur', label: 'Head tilt sustain before alert', min: 1, max: 120, initial: 10, format: seconds },
]

const COOLDOWN: Slider = { key: 'Cooldown', label: 'Notification cooldown', min: 5, max: 600, step: 5, initial: 60, format: seconds }

function SliderRow({ s, last }: { s: Slider; last?: boolean }) {
  const [value, setValue] = useState(s.initial)
  const id = `slider${s.key}`
  return (
    <div className="slider-row" style={last ? { marginBottom: 4 } : undefined}>
      <div className="sr-top"><label htmlFor={id}>{s.label}</label><b>{s.format(value)}</b></div>
      <input type="range" id={id} min={s.min} max={s.max} step={s.step ?? 1} value={value} onChange={e => setValue(Number(e.target.value))} />
    </div>
  )
}

function SliderList({ sliders }: { sliders: Slider[] }) {
  return sliders.map((s, i) => <SliderRow key={s.key} s={s} last={i === sliders.length - 1} />)
}

export default function SettingsTab({ active }: { active: boolean }) {
  const [theme, setTheme] = useState<'paper' | 'dusk'>('paper')

  return (
    <section className={active ? 'panel active' : 'panel'}>
      <div className="preview-note">Loading current thresholds from the backend…</div>
      <div className="settings-grid">
        <div className="card r-a settings-card">
          <h3>Posture sensitivity</h3>
          <p className="sc-sub">Set how much forward lean, tilt, or shoulder rise triggers an alert.</p>
          <SliderList sliders={POSTURE} />
        </div>

        <div className="card r-c settings-card">
          <h3>Eye strain sensitivity</h3>
          <p className="sc-sub">Set the eye narrowing and blink rate that count as strain.</p>
          <SliderList sliders={EYE} />
        </div>

        <div className="card r-b settings-card">
          <h3>Notifications</h3>
          <p className="sc-sub">Choose how often BackTrack can repeat the same alert.</p>
          <SliderRow s={COOLDOWN} last />
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
          <button className="danger-btn">Delete all my data</button>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
        <button className="save-btn">Save preferences</button>
        <button type="button" className="link-btn">Reset thresholds to defaults</button>
      </div>
    </section>
  )
}
