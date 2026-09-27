// Pure helpers that turn the session list into what the History tab shows.

import type { Session } from '../api.ts'

export type Badge = { cls: 'good' | 'warn' | 'neutral'; text: string }
export type BreakdownRow = { label: string; val: number; max: number }
export type Trend = {
  values: number[]
  labels: string[]
  axisLabels: string[]
  current: number
  delta: number
  improved: boolean
  insight: string
}

export function average(arr: number[]): number | null {
  return arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : null
}

function averageBreakdown(sessions: Session[], key: 'posture_breakdown' | 'eye_breakdown', fields: string[]) {
  const rows = sessions.map(s => s[key]).filter((b): b is Record<string, number | null> => b != null)
  const out: Record<string, number | null> = {}
  for (const f of fields) {
    out[f] = average(rows.map(b => b[f]).filter((v): v is number => v != null))
  }
  return out
}

function breakdownRows(spec: [string, number | null, number][]): BreakdownRow[] {
  return spec.filter(([, val]) => val != null).map(([label, val, max]) => ({ label, val: val as number, max }))
}

export function fmtDateShort(iso: string): string {
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ''
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

export function pickLabelSubset(dates: string[]): string[] {
  if (dates.length <= 4) return dates
  const idxs = [0, Math.round((dates.length - 1) / 3), Math.round((dates.length - 1) * 2 / 3), dates.length - 1]
  return [...new Set(idxs)].map(i => dates[i])
}

function postureInsight(trend: Session[]): string {
  const vals = trend.map(s => s.posture_score as number)
  const avgNeck = average(trend.map(s => s.avg_neck_angle).filter((v): v is number => v != null))
  const first = vals[0], last = vals[vals.length - 1]
  const direction = last > first + 2 ? 'trending upward' : last < first - 2 ? 'trending downward' : 'holding fairly steady'
  let text = `Over the last ${vals.length} sessions your posture score is ${direction}, moving from ${Math.round(first)} to ${Math.round(last)}.`
  if (avgNeck != null) text += ` Average neck angle across these sessions was ${avgNeck.toFixed(1)} degrees.`
  return text
}

function eyeInsight(trend: Session[]): string {
  const vals = trend.map(s => s.eye_strain_index as number)
  const avgBlink = average(trend.map(s => s.avg_blink_rate).filter((v): v is number => v != null))
  const first = vals[0], last = vals[vals.length - 1]
  const direction = last > first + 0.5 ? 'climbing' : last < first - 0.5 ? 'easing' : 'holding steady'
  let text = `Your eye strain index is ${direction} across the last ${vals.length} sessions, from ${first.toFixed(1)} to ${last.toFixed(1)}.`
  if (avgBlink != null) text += ` Average blink rate over that span was ${avgBlink.toFixed(1)} per minute.`
  return text
}

function buildTrend(scored: Session[], value: (s: Session) => number, higherIsBetter: boolean, insight: (t: Session[]) => string): Trend | null {
  const trend = scored.slice(-14)
  if (trend.length < 2) return null
  const values = trend.map(value)
  const labels = trend.map(s => fmtDateShort(s.end_time))
  const first = values[0], last = values[values.length - 1]
  return {
    values,
    labels,
    axisLabels: pickLabelSubset(labels),
    current: last,
    delta: Math.abs(last - first),
    improved: higherIsBetter ? last >= first : last <= first,
    insight: insight(trend),
  }
}

export type HistorySummary = {
  sessionCount: number
  avgMinutes: number
  posture: null | {
    average: number
    latest: number
    badge: Badge
    streak: number
    breakdown: BreakdownRow[]
    trend: Trend | null
  }
  eye: null | {
    average: number
    latest: number
    badge: Badge
    latestBlink: number | null
    breakdown: BreakdownRow[]
    trend: Trend | null
  }
}

export function summarizeHistory(sessions: Session[]): HistorySummary {
  // With only one camera a session can have a posture score but no eye
  // score (no face in view) or the reverse, so each metric uses its own list.
  const postureScored = sessions.filter(s => s.posture_score != null)
  const eyeScored = sessions.filter(s => s.eye_strain_index != null)

  const summary: HistorySummary = {
    sessionCount: sessions.length,
    avgMinutes: average(sessions.map(s => s.duration_seconds / 60)) ?? 0,
    posture: null,
    eye: null,
  }

  if (postureScored.length) {
    const scores = postureScored.map(s => s.posture_score as number)
    const b = averageBreakdown(postureScored, 'posture_breakdown', ['neck', 'torso', 'pitch', 'roll', 'shrug'])
    let badge: Badge = { cls: 'neutral', text: 'First session' }
    if (scores.length >= 2) {
      const d = Math.round(scores[scores.length - 1] - scores[scores.length - 2])
      badge = { cls: d >= 0 ? 'good' : 'warn', text: `${d >= 0 ? 'Up' : 'Down'} ${Math.abs(d)} vs last session` }
    }
    let streak = 0
    for (let i = scores.length - 1; i >= 0 && scores[i] > 80; i--) streak++
    summary.posture = {
      average: average(scores) as number,
      latest: scores[scores.length - 1],
      badge,
      streak,
      breakdown: breakdownRows([
        ['Neck angle', b.neck, 40],
        ['Torso lean', b.torso, 30],
        ['Head pitch', b.pitch, 15],
        ['Head roll', b.roll, 15],
        ['Shoulder shrug', b.shrug, 10],
      ]),
      trend: buildTrend(postureScored, s => s.posture_score as number, true, postureInsight),
    }
  }

  if (eyeScored.length) {
    const scores = eyeScored.map(s => s.eye_strain_index as number)
    const b = averageBreakdown(eyeScored, 'eye_breakdown', ['blink', 'ear'])
    let badge: Badge = { cls: 'neutral', text: 'First session' }
    if (scores.length >= 2) {
      const d = Math.round((scores[scores.length - 1] - scores[scores.length - 2]) * 10) / 10
      badge = { cls: d <= 0 ? 'good' : 'warn', text: `${d <= 0 ? 'Down' : 'Up'} ${Math.abs(d)} vs last session` }
    }
    summary.eye = {
      average: average(scores) as number,
      latest: scores[scores.length - 1],
      badge,
      latestBlink: eyeScored[eyeScored.length - 1].avg_blink_rate,
      breakdown: breakdownRows([
        ['Low blink rate', b.blink, 6],
        ['Eye narrowing', b.ear, 4],
      ]),
      trend: buildTrend(eyeScored, s => s.eye_strain_index as number, false, eyeInsight),
    }
  }

  return summary
}
