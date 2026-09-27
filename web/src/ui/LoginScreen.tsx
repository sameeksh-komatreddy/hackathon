import { useState, type FormEvent } from 'react'
import SpineLogo from './SpineLogo.tsx'

export default function LoginScreen({ onSignIn }: { onSignIn: () => void }) {
  const [signup, setSignup] = useState(false)

  function submit(e: FormEvent) {
    e.preventDefault()
    onSignIn()
  }

  return (
    <div id="login-screen">
      <div className="login-card">
        <div className="brand-mark">
          <div className="spine-logo-wrap">
            <SpineLogo width={22} height={26} />
          </div>
          <div className="wordmark">BackTrack<small>Posture and Eye Care</small></div>
        </div>
        <h1>{signup ? 'Create your account' : 'Sign in'}</h1>
        <p className="login-sub">
          {signup ? 'Set up BackTrack to start tracking posture and eye strain.' : 'Track posture and eye strain with care, session by session.'}
        </p>
        <form onSubmit={submit} noValidate>
          {signup && (
            <div className="field">
              <label htmlFor="name">Full name</label>
              <input id="name" type="text" placeholder="Jordan Reyes" />
            </div>
          )}
          <div className="field">
            <label htmlFor="username">Username</label>
            <input id="username" type="text" placeholder="jordanreyes" autoComplete="username" />
          </div>
          <div className="field">
            <label htmlFor="pass">Password</label>
            <input id="pass" type="password" placeholder="Enter your password" autoComplete={signup ? 'new-password' : 'current-password'} />
          </div>
          <button type="submit" className="btn-primary">{signup ? 'Create account' : 'Sign in'}</button>
          <div className="login-error"></div>
        </form>
        <p className="login-foot">
          {signup ? 'Already have an account? ' : 'New to BackTrack? '}
          <button type="button" className="link-btn" onClick={() => setSignup(!signup)}>
            {signup ? 'Sign in instead' : 'Create an account'}
          </button>
        </p>
        <div className="status-strip"><span className="dot-pulse"></span> <span>Checking backend connection&hellip;</span></div>
      </div>
    </div>
  )
}
