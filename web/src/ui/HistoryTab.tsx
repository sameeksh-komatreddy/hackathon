import { useState } from 'react'
import TrendChart, { SPARKLE } from './TrendChart.tsx'

const CHEVRON = <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M6 9l6 6 6-6" /></svg>

type TileProps = {
  cardClass: string
  label: string
  value: string
  unit: string
  breakdown?: boolean
}

function MetricTile({ cardClass, label, value, unit, breakdown }: TileProps) {
  const [open, setOpen] = useState(false)
  return (
    <div className={`card ${cardClass} metric-tile`}>
      <div className="metric-head"><span className="metric-label">{label}</span><span className="metric-badge neutral">No data</span></div>
      <div className="metric-value">{value}<span>{unit}</span></div>
      <div className="metric-foot">No sessions recorded yet</div>
      {breakdown && (
        <>
          <button className={open ? 'score-toggle open' : 'score-toggle'} type="button" aria-expanded={open} onClick={() => setOpen(!open)}>
            <span>{open ? 'Hide score breakdown' : 'See score breakdown'}</span>
            {CHEVRON}
          </button>
          <div className={open ? 'score-breakdown open' : 'score-breakdown'}></div>
        </>
      )}
    </div>
  )
}

function AiCard({ cardClass, title }: { cardClass: string; title: string }) {
  return (
    <div className={`card ${cardClass} ai-insight-card`}>
      <div className="ai-insight-head">
        <div>
          <span className="ai-tag">{SPARKLE} AI-generated report</span>
          <span className="ai-insight-title">{title}</span>
        </div>
        <button className="recal-btn">Refresh</button>
      </div>
      <div className="ai-insight-body">
        <p className="ai-insight-placeholder">Record at least one session to generate a personalized AI report.</p>
      </div>
    </div>
  )
}

export default function HistoryTab({ active }: { active: boolean }) {
  return (
    <section className={active ? 'panel active' : 'panel'}>
      <div className="grid-3">
        <MetricTile cardClass="r-a" label="Average posture score" value="--" unit="out of 100" breakdown />
        <MetricTile cardClass="r-c" label="Eye strain index" value="--" unit="out of 10" breakdown />
        <MetricTile cardClass="r-b" label="Sessions logged" value="0" unit="logged" />
      </div>

      <div className="section-head"><h2>Posture score trend</h2><span className="hint">Most recent sessions</span></div>
      <TrendChart cardClass="r-a" title="Posture Score" color="#5D7052" gradientId="gradPosture" gradientOpacity={0.32} />
      <AiCard cardClass="r-c" title="Posture insight from Gemini" />

      <div className="section-head"><h2>Eye strain trend</h2><span className="hint">Most recent sessions</span></div>
      <TrendChart cardClass="r-c" title="Eye Strain Index" color="#C18C5D" gradientId="gradStrain" gradientOpacity={0.3} currentStyle={{ color: 'var(--destructive)' }} />
      <AiCard cardClass="r-a" title="Eye strain insight from Gemini" />
    </section>
  )
}
