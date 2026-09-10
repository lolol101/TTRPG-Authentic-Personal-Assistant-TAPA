import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api, ApiError } from '@/lib/api'

interface Props {
  onLoggedIn: (token: string) => void
}

export function AuthPanel({ onLoggedIn }: Props) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [notice, setNotice] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setNotice(null)
    setBusy(true)
    try {
      if (mode === 'register') {
        await api.register(email, password)
        setMode('login')
        setNotice('Готово — теперь войди.')
        return
      }
      const { access_token } = await api.login(email, password)
      onLoggedIn(access_token)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Сервер недоступен')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto flex min-h-svh max-w-md items-center px-4">
      <Card className="w-full">
        <CardHeader>
          <CardTitle>{mode === 'login' ? 'Вход' : 'Регистрация'}</CardTitle>
          <CardDescription>TAPA — ассистент по Pathfinder 2e</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Пароль</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
              />
            </div>

            {notice && <p className="text-sm text-muted-foreground">{notice}</p>}
            {error && <p className="text-sm text-destructive">{error}</p>}

            <Button type="submit" className="w-full" disabled={busy}>
              {mode === 'login' ? 'Войти' : 'Зарегистрироваться'}
            </Button>
            <Button
              type="button"
              variant="link"
              className="w-full"
              onClick={() => {
                setMode(mode === 'login' ? 'register' : 'login')
                setError(null)
                setNotice(null)
              }}
            >
              {mode === 'login' ? 'Нет аккаунта? Зарегистрироваться' : 'Уже есть аккаунт? Войти'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
