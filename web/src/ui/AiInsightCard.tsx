import { useCallback, useEffect, useState } from 'react'
import { getInsight, type Insight } from '../api.ts'
import { SPARKLE } from './TrendChart.tsx'

type Props = {
  cardClass: string
  title: string
  metric: 'posture' | 'eye'
  /** Placeholder when there's nothing to report on; null means fetch a report. */
  emptyMessage: string | null
  /** Changes whenever History reloads, so the report is fetched again. */
  reloadKey: number
}

type View =
  | { kind: 'placeholder'; text: string }
  | { kind: 'loading' }
  | { kind: 'error'; text: string }
  | { kind: 'insight'; insight: Insight }

const RISK_LABELS = { good: 'Good standing', moderate: 'Moderate', risky: 'Risky zone' } as const
const INITIAL: View = { kind: 'placeholder', text: 'Record at least one session to generate a personalized AI report.' }

export default function AiInsightCard({ cardClass, title, metric, emptyMessage, reloadKey }: Props) {
  const [fetched, setFetched] = useState<View>(INITIAL)
  // A Refresh pressed since the last History load shows its result even when
  // there is nothing to report on.
  const [refreshedAt, setRefreshedAt] = useState(-1)

  const load = useCallback(async (refresh: boolean) => {
    setFetched({ kind: 'loading' })
    try {
      setFetched({ kind: 'insight', insight: await getInsight(metric, refresh) })
    } catch (err) {
      setFetched({ kind: 'error', text: (err as Error).message })
    }
  }, [metric])

  useEffect(() => {
    // The backend caches reports per session count, so fetching on every
    // History reload is cheap.
    if (reloadKey === 0 || emptyMessage) return
    // eslint-disable-next-line react/set-state-in-effect
    load(false)
  }, [reloadKey, emptyMessage, load])

  const view: View = emptyMessage && refreshedAt !== reloadKey ? { kind: 'placeholder', text: emptyMessage } : fetched

  return (
    <div className={`card ${cardClass} ai-insight-card`}>
      <div className="ai-insight-head">
        <div>
          <span className="ai-tag">{SPARKLE} AI-generated report</span>
          <span className="ai-insight-title">{title}</span>
        </div>
        <button className="recal-btn" onClick={() => { setRefreshedAt(reloadKey); load(true) }}>Refresh</button>
      </div>
      <div className="ai-insight-body">
        {view.kind === 'placeholder' && <p className="ai-insight-placeholder">{view.text}</p>}
        {view.kind === 'loading' && (
          <p className="ai-insight-placeholder">
            Generating your personalized report<span className="ai-loading-dots"><span></span><span></span><span></span></span>
          </p>
        )}
        {view.kind === 'error' && <p className="ai-insight-error">{view.text}</p>}
        {view.kind === 'insight' && <InsightBody insight={view.insight} />}
      </div>
    </div>
  )
}

function InsightBody({ insight }: { insight: Insight }) {
  const raw = String(insight?.risk_level ?? 'moderate').toLowerCase()
  const risk = (raw in RISK_LABELS ? raw : 'moderate') as keyof typeof RISK_LABELS
  const suggestions = Array.isArray(insight?.suggestions) ? insight.suggestions : []
  return (
    <>
      <span className={`ai-risk-badge ${risk}`}>{RISK_LABELS[risk]}</span>
      {insight?.summary && <p className="ai-summary">{insight.summary}</p>}
      {suggestions.length > 0 && (
        <ul className="ai-suggestions">{suggestions.map((s, i) => <li key={i}>{s}</li>)}</ul>
      )}
    </>
  )
}
