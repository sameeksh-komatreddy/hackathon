const CHECKS = [
  { id: 'chkPosture', title: 'Posture data', desc: 'Session scores, angle readings, and drift patterns', checked: true },
  { id: 'chkEye', title: 'Eye strain data', desc: 'Blink rate and strain index history', checked: true },
  { id: 'chkTrend', title: 'Trend summary', desc: 'Session over session changes and automated insights', checked: false },
  { id: 'chkSessions', title: 'Session log', desc: 'Full list of individual sessions with duration and averages', checked: false },
]

export default function ExportTab({ active }: { active: boolean }) {
  return (
    <section className={active ? 'panel active' : 'panel'}>
      <div className="preview-note">Pulling your session history from the backend…</div>
      <div className="export-layout">
        <div>
          <div className="section-head" style={{ marginTop: 0 }}><h2>Include in report</h2></div>
          <ul className="check-list">
            {CHECKS.map(c => (
              <li className="check-item" key={c.id}>
                <input type="checkbox" id={c.id} defaultChecked={c.checked} />
                <div className="ci-text"><b>{c.title}</b><span>{c.desc}</span></div>
              </li>
            ))}
          </ul>

          <div className="range-row">
            <div className="field"><label htmlFor="exportFrom">From</label><input type="date" id="exportFrom" /></div>
            <div className="field"><label htmlFor="exportTo">To</label><input type="date" id="exportTo" /></div>
          </div>

          <button className="pdf-btn">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 3v12" /><path d="M7 10l5 5 5-5" /><path d="M4 19h16" /></svg>
            Generate PDF report
          </button>
          <p className="rec-note">Built to hand to a physical therapist or doctor: plain figures, no jargon, one section per category.</p>
        </div>

        <div className="card r-b report-preview">
          <div className="report-sheet">
            <div className="rs-head"><b>BackTrack Report</b><span>--</span></div>
            <div className="rs-row"><span>Patient</span><b>BackTrack User</b></div>
            <div className="rs-row"><span>Range</span><b>--</b></div>
            <div className="rs-row"><span>Average posture score</span><b>-- out of 100</b></div>
            <div className="rs-row"><span>Average eye strain index</span><b>-- out of 10</b></div>
            <div className="rs-block"></div>
            <div className="rs-row"><span>Sessions included</span><b>0</b></div>
            <div className="rs-row" style={{ borderBottom: 'none' }}><span>Format</span><b>PDF</b></div>
          </div>
        </div>
      </div>
    </section>
  )
}
