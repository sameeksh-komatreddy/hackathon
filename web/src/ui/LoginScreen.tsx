import { useEffect, useState, type FormEvent } from 'react'
import { checkBackend, signIn, signUp, type User } from '../api.ts'
import SpineLogo from './SpineLogo.tsx'

export default function LoginScreen({ onSignIn }: { onSignIn: (user: User) => void }) {
  const [signup, setSignup] = useState(false)
  const [name, setName] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [online, setOnline] = useState<boolean | null>(null)

  useEffect(() => {
    checkBackend().then(setOnline)
  }, [])

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError('')
    const user = username.trim()
    if (!user || !password) {
      setError('Enter a username and password.')
      return
    }
    setBusy(true)
    try {
      onSignIn(signup ? await signUp(user, password, name.trim()) : await signIn(user, password))
    } catch (err) {
      setError((err as Error).message)
      setBusy(false)
    }
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
              <input id="name" type="text" placeholder="Jordan Reyes" value={name} onChange={e => setName(e.target.value)} />
            </div>
          )}
          <div className="field">
            <label htmlFor="username">Username</label>
            <input id="username" type="text" placeholder="jordanreyes" autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="pass">Password</label>
            <input id="pass" type="password" placeholder="Enter your password" autoComplete={signup ? 'new-password' : 'current-password'}
              value={password} onChange={e => setPassword(e.target.value)} />
          </div>
          <button type="submit" className="btn-primary" disabled={busy}>
            {busy ? (signup ? 'Creating account…' : 'Signing in…') : (signup ? 'Create account' : 'Sign in')}
          </button>
          <div className={error ? 'login-error show' : 'login-error'} role="alert">{error}</div>
        </form>
        <p className="login-foot">
          {signup ? 'Already have an account? ' : 'New to BackTrack? '}
          <button type="button" className="link-btn" onClick={() => { setSignup(!signup); setError('') }}>
            {signup ? 'Sign in instead' : 'Create an account'}
          </button>
        </p>
        <div className="status-strip">
          <span className={online === false ? 'dot-pulse offline' : 'dot-pulse'}></span>{' '}
          <span>
            {online == null ? <>Checking backend connection&hellip;</>
              : online ? 'Backend connected — ready to sign in'
              : "Couldn't reach the BackTrack backend at 127.0.0.1:5050"}
          </span>
        </div>
      </div>
    </div>
  )
}
