import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import App from './App.tsx'

describe('App', () => {
  it('signs in and switches between all four tabs', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(screen.getByText('Review sessions and long-term trends.')).toBeInTheDocument()
    expect(screen.getByText('Posture score trend').closest('section')).toHaveClass('active')

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

  it('shows the name field only when creating an account', async () => {
    const user = userEvent.setup()
    render(<App />)
    expect(screen.queryByLabelText('Full name')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Create an account' }))
    expect(screen.getByLabelText('Full name')).toBeInTheDocument()
  })
})
