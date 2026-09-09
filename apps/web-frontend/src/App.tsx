import { useState } from 'react'
import './App.css'

interface UserResponse {
  id: number
  email: string
}

interface TokenResponse {
  access_token: string
  token_type: string
}

type Mode = 'login' | 'register'

async function parseErrorDetail(response: Response): Promise<string> {
  try {
    const body = await response.json()
    return typeof body.detail === 'string' ? body.detail : response.statusText
  } catch {
    return response.statusText
  }
}

function App() {
  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [token, setToken] = useState<string | null>(null)
  const [me, setMe] = useState<UserResponse | null>(null)
  const [pingResult, setPingResult] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)

    if (mode === 'register') {
      const response = await fetch('/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      if (!response.ok) {
        setError(await parseErrorDetail(response))
        return
      }
      setMode('login')
      setError('Registered — now log in.')
      return
    }

    const response = await fetch('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    })
    if (!response.ok) {
      setError(await parseErrorDetail(response))
      return
    }
    const data: TokenResponse = await response.json()
    setToken(data.access_token)
    setMe(null)
  }

  async function fetchMe() {
    if (!token) return
    setError(null)
    const response = await fetch('/auth/me', {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!response.ok) {
      setError(await parseErrorDetail(response))
      return
    }
    setMe(await response.json())
  }

  async function pingLlmService() {
    setError(null)
    setPingResult(null)
    const response = await fetch('/llm/ping')
    if (!response.ok) {
      setError(await parseErrorDetail(response))
      return
    }
    setPingResult(JSON.stringify(await response.json()))
  }

  function logOut() {
    setToken(null)
    setMe(null)
  }

  return (
    <main className="skeleton">
      <h1>TAPA — service skeleton</h1>

      {!token ? (
        <form onSubmit={handleSubmit}>
          <h2>{mode === 'login' ? 'Log in' : 'Register'}</h2>
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
            />
          </label>
          <button type="submit">{mode === 'login' ? 'Log in' : 'Register'}</button>
          <button
            type="button"
            className="link"
            onClick={() => setMode(mode === 'login' ? 'register' : 'login')}
          >
            {mode === 'login' ? 'Need an account? Register' : 'Have an account? Log in'}
          </button>
        </form>
      ) : (
        <div>
          <p>Logged in. Token stored in memory only (not persisted).</p>
          <button type="button" onClick={fetchMe}>
            GET /auth/me
          </button>
          <button type="button" onClick={logOut}>
            Log out
          </button>
          {me && (
            <pre>
              {JSON.stringify(me, null, 2)}
            </pre>
          )}
        </div>
      )}

      <hr />

      <div>
        <h2>Connectivity check</h2>
        <button type="button" onClick={pingLlmService}>
          ping llm-service (via backend)
        </button>
        {pingResult && <pre>{pingResult}</pre>}
      </div>

      {error && <p className="error">{error}</p>}
    </main>
  )
}

export default App
