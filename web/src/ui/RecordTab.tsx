import type { ReactNode } from 'react'

const THRESHOLDS = ['Eye narrowing', 'Head tilt', 'Blink rate', 'Shoulder shrug', 'Hunching']

type CamProps = {
  cardClass: string
  name: string
  icon: ReactNode
  feet: [string, string]
}

function CamPanel({ cardClass, name, icon, feet }: CamProps) {
  return (
    <div className={`card ${cardClass} cam-panel`}>
      <div className="cam-head">
        <span className="cam-name">{icon} {name}</span>
        <span className="cam-status offline"><span className="dot"></span>Not tracking</span>
        <button className="recal-btn">Recalibrate</button>
      </div>
      <div className="cam-view">
        <img className="cam-feed-img hidden" alt={`${name} feed`} />
        <div className="cam-placeholder">
          <span className="dot-pulse offline"></span>
          <span>Connecting to the {name.toLowerCase()}…</span>
        </div>
      </div>
      <div className="cam-foot"><span>{feet[0]} <b>0.0 degrees</b></span><span>{feet[1]} <b>0.0 degrees</b></span></div>
    </div>
  )
}

export default function RecordTab({ active }: { active: boolean }) {
  return (
    <section className={active ? 'panel active' : 'panel'}>
      <div className="preview-note">Press Start recording to connect to the BackTrack backend at 127.0.0.1:5050.</div>

      <div className="card r-b cam-setup">
        <div className="threshold-panel-head">
          <span className="threshold-panel-title">Cameras</span>
          <div className="cam-setup-actions">
            <button className="threshold-test-btn" type="button">Swap</button>
            <button className="threshold-test-btn" type="button">Rescan</button>
          </div>
        </div>
        <div className="cam-setup-grid">
          <label className="cam-slot">
            <span className="cam-slot-label">Front camera <em>faces you: eyes, head tilt, shoulders</em></span>
            <select></select>
            <span className="cam-slot-state"></span>
          </label>
          <label className="cam-slot">
            <span className="cam-slot-label">Side camera <em>from your side: neck and back angle</em></span>
            <select></select>
            <span className="cam-slot-state"></span>
          </label>
        </div>

        <div className="phone-link">
          <div className="phone-qr" aria-label="QR code to open the phone camera page"></div>
          <div className="phone-steps">
            <div className="phone-steps-title">Use your phone as a camera</div>
            <ol>
              <li>Connect your phone to the same Wi-Fi as this computer.</li>
              <li>Scan this code with your phone's camera.</li>
              <li>Your phone will warn that the connection isn't private. That's expected: the link stays on your Wi-Fi. Tap <b>Show Details → visit this website</b> (iPhone) or <b>Advanced → Proceed</b> (Android). You only do this once.</li>
              <li>Tap <b>Start camera</b> and allow camera access. Stand the phone to your side at about shoulder height.</li>
            </ol>
            <div className="phone-url-row">Or type this address: <code>loading…</code></div>
            <div className="phone-status-row">
              <span className="cam-status offline"><span className="dot"></span>No phone yet</span>
              <button className="threshold-test-btn" type="button">New code</button>
            </div>
            <details className="phone-help">
              <summary>Phone can't connect?</summary>
              <ul>
                <li><b>Firewall:</b> the first time BackTrack runs, Windows or macOS asks whether Python may accept connections. Allow it on private networks. On Linux, open port 5051 (e.g. <code>sudo ufw allow 5051/tcp</code>).</li>
                <li><b>School, work or guest Wi-Fi</b> often stops devices from reaching each other. Turn on your phone's hotspot, connect this computer to it, then press <b>New code</b>.</li>
                <li><b>Wrong network address:</b> if this computer has several network adapters, try one of these instead: <span>none</span></li>
              </ul>
            </details>
          </div>
        </div>
      </div>

      <div className="rec-grid">
        <CamPanel
          cardClass="r-a"
          name="Front camera"
          icon={<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2" y="6" width="14" height="12" rx="2" /><path d="M16 10l6-4v12l-6-4" /></svg>}
          feet={['Head pitch', 'Head roll']}
        />
        <CamPanel
          cardClass="r-c"
          name="Side camera"
          icon={<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="7" y="2" width="10" height="20" rx="2" /><line x1="11" y1="18" x2="13" y2="18" /></svg>}
          feet={['Neck angle', 'Torso lean']}
        />
      </div>

      <div className="rec-controls">
        <button className="record-btn"><span className="rec-dot"></span><span>Start recording</span></button>
        <span className="rec-timer">00:00:00</span>
      </div>
      <p className="rec-note">Notifications will alert you when posture or eye strain thresholds are crossed, both as pop-ups here and as system notifications on your device, for as long as a session is recording — even if another window is focused.</p>

      <div className="card r-b threshold-panel">
        <div className="threshold-panel-head">
          <span className="threshold-panel-title">Notification thresholds</span>
          <button className="threshold-test-btn" type="button">Send test notification</button>
        </div>
        <div className="threshold-grid">
          {THRESHOLDS.map(label => (
            <div className="threshold-item" key={label}>
              <div className="threshold-item-top"><span className="threshold-item-label">{label}</span><span className="threshold-item-pct">0%</span></div>
              <div className="threshold-track"><div className="threshold-fill"></div></div>
            </div>
          ))}
        </div>
        <p className="threshold-hint">Each bar fills as that specific issue is sustained. When one is full, a notification fires natively on your device — on screen over anything else you have open — not just inside this page.</p>
      </div>

      <div className="section-head"><h2>Live readout</h2><span className="hint">Updating from the backend stream</span></div>
      <div className="live-metrics">
        <div className="card r-a live-metric">
          <div className="lm-label">Neck angle</div><div className="lm-val">0.0 degrees</div>
          <div className="bar-track"><div className="bar-fill" style={{ width: '0%' }}></div></div>
        </div>
        <div className="card r-b live-metric">
          <div className="lm-label">Blink rate</div>
          <div className="lm-val">0<span style={{ fontSize: 13, color: 'var(--muted-fg)', fontFamily: 'var(--font-body)' }}> per minute</span></div>
          <div className="bar-track"><div className="bar-fill" style={{ width: '0%', background: 'linear-gradient(90deg,var(--destructive),var(--secondary))' }}></div></div>
        </div>
        <div className="card r-c live-metric">
          <div className="lm-label">Elapsed</div><div className="lm-val">00:00</div>
          <div className="bar-track"><div className="bar-fill" style={{ width: '0%' }}></div></div>
        </div>
      </div>
    </section>
  )
}
