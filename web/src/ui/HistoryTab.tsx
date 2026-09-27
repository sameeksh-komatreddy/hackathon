import { useEffect, useState, type ReactNode } from 'react'
import { getSessions } from '../api.ts'
import { useApp } from './AppContext.tsx'
import AiInsightCard from './AiInsightCard.tsx'
import TrendChart from './TrendChart.tsx'
import { summarizeHistory, type Badge, type BreakdownRow, type HistorySummary } from './history.ts'

const CHEVRON = <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M6 9l6 6 6-6" /></svg>
const NO_DATA: Badge = { cls: 'neutral', text: 'No data' }
const AI_DEFAULT = 'Record at least one session to generate a personalized AI report.'

type TileProps = {
  cardClass: string
  label: string
  badge: Badge
  value: ReactNode
  unit: string
  foot: ReactNode
  breakdown?: BreakdownRow[]
}

function MetricTile({ cardClass, label, badge, value, unit, foot, breakdown }: TileProps) {
  const [open, setOpen] = useState(false)
  return (
    <div className={`card ${cardClass} metric-tile`}>
      <div className="metric-head"><span className="metric-label">{label}</span><span className={`metric-badge ${badge.cls}`}>{badge.text}</span></div>
      <div className="metric-value">{value}<span>{unit}</span></div>
      <div className="metric-foot">{foot}</div>
      {breakdown && (
        <>
          <button className={open ? 'score-toggle open' : 'score-toggle'} type="button" aria-expanded={open} onClick={() => setOpen(!open)}>
            <span>{open ? 'Hide score breakdown' : 'See score breakdown'}</span>
            {CHEVRON}
          </button>
          <div className={open ? 'score-breakdown open' : 'score-breakdown'}>
            {breakdown.length === 0 ? (
              <div className="breakdown-empty">Not enough data yet to break this down.</div>
            ) : breakdown.map(r => (
              <div className="breakdown-row" key={r.label}>
                <div className="bd-left">
                  <span className="bd-label">{r.label}</span>
                  <div className="breakdown-bar"><div className="breakdown-bar-fill" style={{ width: Math.max(0, Math.min(100, (r.val / r.max) * 100)).toFixed(0) + '%' }}></div></div>
                </div>
                <b>-{r.val.toFixed(1)}</b>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

function plural(n: number, word: string) {
  return `${n} ${word}${n === 1 ? '' : 's'}`
}

function Change({ up, good, amount }: { up: boolean; good: boolean; amount: string }) {
  return <span style={{ fontSize: 13, color: good ? 'var(--primary)' : 'var(--destructive)' }}>{up ? 'up ' : 'down '}{amount}</span>
}

type Props = { active: boolean; onLatestScore: (score: number | null) => void }

export default function HistoryTab({ active, onLatestScore }: Props) {
  const { dataVersion } = useApp()
  const [summary, setSummary] = useState<HistorySummary | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const [loads, setLoads] = useState(0)

  useEffect(() => {
    if (!active) return
    let cancelled = false
    getSessions(30).then(sessions => {
      if (cancelled) return
      const s = summarizeHistory(sessions)
      const empty = !s.posture && !s.eye
      setSummary(empty ? null : s)
      setNote(empty ? 'No completed sessions yet. Head to the Record tab and press Start recording to log your first session.' : null)
      onLatestScore(s.posture ? Math.round(s.posture.latest) : null)
      setLoads(n => n + 1)
    }, () => {
      if (cancelled) return
      setSummary(null)
      setNote("Couldn't reach the BackTrack backend at 127.0.0.1:5050. Start it and reload this tab to see your history.")
      setLoads(n => n + 1)
    })
    return () => { cancelled = true }
  }, [active, dataVersion, onLatestScore])

  const p = summary?.posture ?? null
  const e = summary?.eye ?? null
  const avgMin = summary ? Math.round(summary.avgMinutes) : 0

  const postureFoot = !summary ? 'No sessions recorded yet'
    : !p ? 'No posture data yet — make sure a camera can see you'
    : p.streak > 0 ? <>Current streak: <b>{plural(p.streak, 'session')}</b> above 80</>
    : 'No active streak above 80 right now'
  const eyeFoot = !summary ? 'No sessions recorded yet'
    : !e ? 'Eye tracking needs the front camera to see your face'
    : e.latestBlink != null ? <>Latest avg blink rate: <b>{e.latestBlink} per minute</b></>
    : 'No blink data recorded yet'

  const postureCurrent = p?.trend
    ? <>{Math.round(p.trend.current)} <Change up={p.trend.improved} good={p.trend.improved} amount={String(Math.round(p.trend.delta))} /></>
    : p ? Math.round(p.latest) : '--'
  const eyeCurrent = e?.trend
    ? <>{e.trend.current.toFixed(1)} <Change up={!e.trend.improved} good={e.trend.improved} amount={e.trend.delta.toFixed(1)} /></>
    : e ? e.latest.toFixed(1) : '--'

  return (
    <section className={active ? 'panel active' : 'panel'}>
      {note && <div className="preview-note">{note}</div>}

      <div className="grid-3">
        <MetricTile cardClass="r-a" label="Average posture score" badge={p?.badge ?? NO_DATA}
          value={p ? Math.round(p.average) : '--'} unit="out of 100" foot={postureFoot} breakdown={p?.breakdown ?? []} />
        <MetricTile cardClass="r-c" label="Eye strain index" badge={e?.badge ?? NO_DATA}
          value={e ? e.average.toFixed(1) : '--'} unit="out of 10" foot={eyeFoot} breakdown={e?.breakdown ?? []} />
        <MetricTile cardClass="r-b" label="Sessions logged"
          badge={summary ? { cls: 'neutral', text: plural(summary.sessionCount, 'session') } : NO_DATA}
          value={summary ? summary.sessionCount : 0} unit="logged"
          foot={summary ? <>Average length: <b>{plural(avgMin, 'minute')}</b></> : 'No sessions recorded yet'} />
      </div>

      <div className="section-head"><h2>Posture score trend</h2><span className="hint">Most recent sessions</span></div>
      <TrendChart cardClass="r-a" title="Posture Score" color="#5D7052" gradientId="gradPosture" gradientOpacity={0.32}
        maxValue={100} trend={p?.trend ?? null} current={postureCurrent} fmtValue={v => Math.round(v) + ' / 100'} />
      <AiInsightCard cardClass="r-c" title="Posture insight from Gemini" metric="posture" reloadKey={loads}
        emptyMessage={!summary ? AI_DEFAULT : !p ? 'Record a session where a camera can see you to get a posture report.' : null} />

      <div className="section-head"><h2>Eye strain trend</h2><span className="hint">Most recent sessions</span></div>
      <TrendChart cardClass="r-c" title="Eye Strain Index" color="#C18C5D" gradientId="gradStrain" gradientOpacity={0.3}
        maxValue={10} trend={e?.trend ?? null} current={eyeCurrent} currentColor="var(--destructive)" fmtValue={v => v.toFixed(1) + ' / 10'} />
      <AiInsightCard cardClass="r-a" title="Eye strain insight from Gemini" metric="eye" reloadKey={loads}
        emptyMessage={!summary ? AI_DEFAULT : !e ? "Eye reports need a session where the front camera could see your face." : null} />
    </section>
  )
}
