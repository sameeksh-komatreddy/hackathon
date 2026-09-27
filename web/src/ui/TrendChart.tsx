import type { CSSProperties } from 'react'

type Props = {
  cardClass: string
  title: string
  color: string
  gradientId: string
  gradientOpacity: number
  currentStyle?: CSSProperties
}

const SPARKLE = <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2l2.4 6.6L21 11l-6.6 2.4L12 20l-2.4-6.6L3 11l6.6-2.4z" /></svg>

/** Session trend line. Empty state only until S02b feeds it points. */
export default function TrendChart({ cardClass, title, color, gradientId, gradientOpacity, currentStyle }: Props) {
  const hasData = false
  return (
    <div className={`card ${cardClass} chart-card`}>
      <div className="chart-top"><span className="chart-title">{title}</span><span className="chart-current" style={currentStyle}>--</span></div>
      <div className="chart-empty">Record at least two sessions from the Record tab to see a trend line here.</div>
      <div className={hasData ? undefined : 'hidden'}>
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
          <polyline points="" fill="none" stroke={color} strokeWidth="2.75" strokeLinecap="round" strokeLinejoin="round" />
          <polygon points="" fill={`url(#${gradientId})`} />
          <circle className="chart-hover-dot" cx="0" cy="0" r="6" fill={color} />
          <circle cx="0" cy="0" r="5" fill={color} />
          <g></g>
        </svg>
        <div className="chart-tooltip hidden"></div>
        <div className="chart-axis-labels"></div>
        <div className="insight-box">
          <div className="tag">{SPARKLE} Session insight</div>
          <p></p>
        </div>
      </div>
    </div>
  )
}

export { SPARKLE }
