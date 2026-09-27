import { useRef, useState, type MouseEvent, type ReactNode } from 'react'
import type { Trend } from './history.ts'

type Props = {
  cardClass: string
  title: string
  color: string
  gradientId: string
  gradientOpacity: number
  maxValue: number
  trend: Trend | null
  /** Shown in the corner: the latest value and change, or '--'. */
  current: ReactNode
  currentColor?: string
  fmtValue: (v: number) => string
}

export const SPARKLE = <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2l2.4 6.6L21 11l-6.6 2.4L12 20l-2.4-6.6L3 11l6.6-2.4z" /></svg>

type Hover = { i: number; left: number; top: number }

export default function TrendChart(props: Props) {
  const { cardClass, title, color, gradientId, gradientOpacity, maxValue, trend, current, currentColor, fmtValue } = props
  const cardRef = useRef<HTMLDivElement>(null)
  const [hover, setHover] = useState<Hover | null>(null)

  const n = trend ? trend.values.length : 0
  const pts = trend
    ? trend.values.map((v, i) => [
        n === 1 ? 0 : (i / (n - 1)) * 600,
        150 - Math.max(0, Math.min(1, v / maxValue)) * 130 - 10,
      ])
    : []
  const ptsStr = pts.map(p => p[0].toFixed(1) + ',' + p[1].toFixed(1)).join(' ')
  const last = pts[pts.length - 1] ?? [0, 0]

  function track(i: number, e: MouseEvent) {
    const rect = cardRef.current?.getBoundingClientRect()
    if (!rect) return
    setHover({ i, left: e.clientX - rect.left, top: e.clientY - rect.top })
  }

  return (
    <div className={`card ${cardClass} chart-card`} ref={cardRef}>
      <div className="chart-top"><span className="chart-title">{title}</span><span className="chart-current" style={currentColor ? { color: currentColor } : undefined}>{current}</span></div>
      {!trend ? (
        <div className="chart-empty">Record at least two sessions from the Record tab to see a trend line here.</div>
      ) : (
        <div>
          <svg className="chart" viewBox="0 0 600 150" preserveAspectRatio="none">
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color} stopOpacity={gradientOpacity} />
                <stop offset="100%" stopColor={color} stopOpacity="0" />
              </linearGradient>
            </defs>
            <g stroke="#DED8CF" strokeWidth="1">
              <line x1="0" y1="30" x2="600" y2="30" /><line x1="0" y1="75" x2="600" y2="75" /><line x1="0" y1="120" x2="600" y2="120" />
            </g>
            <polyline points={ptsStr} fill="none" stroke={color} strokeWidth="2.75" strokeLinecap="round" strokeLinejoin="round" />
            <polygon points={ptsStr + ' 600,150 0,150'} fill={`url(#${gradientId})`} />
            <circle
              className={hover ? 'chart-hover-dot visible' : 'chart-hover-dot'}
              cx={hover ? pts[hover.i][0].toFixed(1) : 0}
              cy={hover ? pts[hover.i][1].toFixed(1) : 0}
              r="6" fill={color}
            />
            <circle cx={last[0].toFixed(1)} cy={last[1].toFixed(1)} r="5" fill={color} />
            <g>
              {pts.map((p, i) => (
                <circle
                  key={i}
                  className="chart-hit"
                  cx={p[0].toFixed(1)} cy={p[1].toFixed(1)} r="12"
                  onMouseEnter={e => track(i, e)}
                  onMouseMove={e => track(i, e)}
                  onMouseLeave={() => setHover(null)}
                />
              ))}
            </g>
          </svg>
          {hover && (
            <div className="chart-tooltip" style={{ left: hover.left, top: hover.top }}>
              <b>{fmtValue(trend.values[hover.i])}</b><span>{trend.labels[hover.i]}</span>
            </div>
          )}
          <div className="chart-axis-labels">
            {trend.axisLabels.map((l, i) => <span key={i}>{l}</span>)}
          </div>
          <div className="insight-box">
            <div className="tag">{SPARKLE} Session insight</div>
            <p>{trend.insight}</p>
          </div>
        </div>
      )}
    </div>
  )
}
