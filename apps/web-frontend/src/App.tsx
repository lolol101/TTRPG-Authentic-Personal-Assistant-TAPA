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

interface AskSource {
  title: string
  url: string
  source_book: string
}

interface AskResponse {
  answer: string
  sources: AskSource[]
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
  const [question, setQuestion] = useState('')
  const [asking, setAsking] = useState(false)
  const [askResult, setAskResult] = useState<AskResponse | null>(null)
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

  async function askQuestion(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setAskResult(null)
    setAsking(true)
    try {
      const response = await fetch('/llm/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      })
      if (!response.ok) {
        setError(await parseErrorDetail(response))
        return
      }
      setAskResult(await response.json())
    } finally {
      setAsking(false)
    }
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
        <h2>Спросить по PF2e</h2>
        <form onSubmit={askQuestion}>
          <label>
            Вопрос (сейчас в базе только раздел /actions/)
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Что делает действие Удар?"
              required
            />
          </label>
          <button type="submit" disabled={asking}>
            {asking ? 'Спрашиваю…' : 'Спросить'}
          </button>
        </form>
        {askResult && (
          <div>
            <p>{askResult.answer}</p>
            {askResult.sources.length > 0 && (
              <ul>
                {askResult.sources.map((source) => (
                  <li key={source.url}>
                    <a href={source.url} target="_blank" rel="noreferrer">
                      {source.title}
                    </a>
                    {source.source_book && ` — ${source.source_book}`}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

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
