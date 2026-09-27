import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import * as api from '../api.ts'
import { baseRoutes, mockBackend } from '../test/mockBackend.ts'
import App from './App.tsx'

afterEach(async () => {
  mockBackend(baseRoutes)
  await api.signOut() // forget the token between tests
  vi.unstubAllGlobals()
})

async function signIn() {
  const user = userEvent.setup()
  render(<App />)
  await user.type(screen.getByLabelText('Username'), 'jordan')
  await user.type(screen.getByLabelText('Password'), 'secret1')
  await user.click(screen.getByRole('button', { name: 'Sign in' }))
  await screen.findByText('Review sessions and long-term trends.')
  return user
}

describe('App', () => {
  it('signs in and switches between all four tabs', async () => {
    const calls = mockBackend(baseRoutes)
    const user = await signIn()

    expect(screen.getByText('JR')).toBeInTheDocument()
    expect(calls.find(c => c.path === '/sessions')?.headers.Authorization).toBe('Bearer tok123')

    const cases = [
      ['Record', 'Capture a new session from both camera angles.', 'Live readout'],
      ['Export', 'Turn your history into a report you can share.', 'Include in report'],
      ['Settings', 'Tune thresholds, reminders, and appearance.', 'Posture sensitivity'],
      ['History', 'Review sessions and long-term trends.', 'Posture score trend'],
    ]
    for (const [tab, subtitle, heading] of cases) {
      await user.click(screen.getByRole('button', { name: tab }))
      expect(screen.getByText(subtitle)).toBeInTheDocument()
      expect(screen.getByText(heading).closest('section')).toHaveClass('active')
      expect(document.querySelectorAll('section.panel.active')).toHaveLength(1)
    }
  })

  it("shows the backend's error when sign-in fails", async () => {
    mockBackend({ ...baseRoutes, 'POST /auth/login': Response.json({ ok: false, error: 'Incorrect username or password.' }, { status: 401 }) })
    const user = userEvent.setup()
    render(<App />)
    await user.type(screen.getByLabelText('Username'), 'jordan')
    await user.type(screen.getByLabelText('Password'), 'wrong!!')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect username or password.')
  })

  it('shows the name field only when creating an account', async () => {
    mockBackend(baseRoutes)
    const user = userEvent.setup()
    render(<App />)
    expect(screen.queryByLabelText('Full name')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Create an account' }))
    expect(screen.getByLabelText('Full name')).toBeInTheDocument()
  })

  it('stops a running recording before signing out', async () => {
    const calls = mockBackend({
      ...baseRoutes,
      'GET /session/status': { recording: true, start_time: Date.now() / 1000 },
      'POST /session/stop': { ok: true, session: null },
    })
    const user = await signIn()
    await user.click(screen.getByRole('button', { name: 'Sign out' }))
    await screen.findByRole('button', { name: 'Sign in' })
    const paths = calls.map(c => `${c.method} ${c.path}`)
    expect(paths.indexOf('POST /session/stop')).toBeGreaterThan(-1)
    expect(paths.indexOf('POST /session/stop')).toBeLessThan(paths.indexOf('POST /auth/logout'))
  })

  it("the AI Refresh button doesn't recalibrate a camera", async () => {
    const calls = mockBackend({ ...baseRoutes, 'GET /insights/posture': { ok: true, insight: { risk_level: 'good', summary: 'Fine.' } } })
    const user = await signIn()
    await user.click(screen.getAllByRole('button', { name: 'Refresh' })[0])
    await waitFor(() => expect(calls.some(c => c.path === '/insights/posture')).toBe(true))
    expect(calls.some(c => c.path.startsWith('/recalibrate'))).toBe(false)
  })
})
