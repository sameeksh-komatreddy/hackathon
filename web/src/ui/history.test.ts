import { describe, expect, it } from 'vitest'
import type { Session } from '../api.ts'
import { pickLabelSubset, summarizeHistory } from './history.ts'

function session(day: number, posture: number | null, eye: number | null, extra: Partial<Session> = {}): Session {
  const iso = `2026-09-${String(day).padStart(2, '0')}T10:00:00`
  return {
    id: String(day), start_time: iso, end_time: iso, duration_seconds: 600,
    posture_score: posture, eye_strain_index: eye,
    avg_neck_angle: null, avg_torso_angle: null, avg_blink_rate: null,
    ...extra,
  }
}

describe('summarizeHistory', () => {
  it('returns no metrics when nothing was scored', () => {
    const s = summarizeHistory([session(1, null, null)])
    expect(s.posture).toBeNull()
    expect(s.eye).toBeNull()
    expect(s.sessionCount).toBe(1)
  })

  it('scores posture and eye from their own session lists', () => {
    const s = summarizeHistory([session(1, 70, null), session(2, null, 4), session(3, 90, 6)])
    expect(s.posture?.average).toBe(80)
    expect(s.eye?.average).toBe(5)
    expect(s.posture?.badge).toEqual({ cls: 'good', text: 'Up 20 vs last session' })
    // eye strain going up is bad
    expect(s.eye?.badge).toEqual({ cls: 'warn', text: 'Up 2 vs last session' })
  })

  it('counts the streak of sessions above 80 from the latest back', () => {
    const s = summarizeHistory([session(1, 85, null), session(2, 70, null), session(3, 81, null), session(4, 95, null)])
    expect(s.posture?.streak).toBe(2)
  })

  it('needs two sessions for a trend and keeps the last 14', () => {
    expect(summarizeHistory([session(1, 70, null)]).posture?.trend).toBeNull()
    const many = Array.from({ length: 20 }, (_, i) => session(i + 1, 50 + i, null))
    const trend = summarizeHistory(many).posture?.trend
    expect(trend?.values).toHaveLength(14)
    expect(trend?.values[0]).toBe(56)
    expect(trend?.improved).toBe(true)
    expect(trend?.insight).toContain('trending upward')
  })

  it('averages breakdowns and drops rows with no data', () => {
    const s = summarizeHistory([
      session(1, 80, null, { posture_breakdown: { neck: 4, torso: null, pitch: 1, roll: null, shrug: null } }),
      session(2, 80, null, { posture_breakdown: { neck: 6, torso: null, pitch: 3, roll: null, shrug: null } }),
    ])
    expect(s.posture?.breakdown).toEqual([
      { label: 'Neck angle', val: 5, max: 40 },
      { label: 'Head pitch', val: 2, max: 15 },
    ])
  })
})

describe('pickLabelSubset', () => {
  it('keeps up to four evenly spread labels', () => {
    expect(pickLabelSubset(['a', 'b', 'c'])).toEqual(['a', 'b', 'c'])
    expect(pickLabelSubset(['a', 'b', 'c', 'd', 'e', 'f', 'g'])).toEqual(['a', 'c', 'e', 'g'])
  })
})
