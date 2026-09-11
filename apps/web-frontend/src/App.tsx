import { useCallback, useEffect, useState } from 'react'
import { AuthPanel } from '@/components/AuthPanel'
import { CharacterList } from '@/components/CharacterList'
import { ChatPanel } from '@/components/ChatPanel'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { api, ApiError, type Character, type CharacterUpdate } from '@/lib/api'
import { rulesetById, rulesetLabel } from '@/rulesets/registry'

const TOKEN_STORAGE_KEY = 'tapa.token'

function App() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_STORAGE_KEY))
  const [email, setEmail] = useState<string | null>(null)
  const [characters, setCharacters] = useState<Character[]>([])
  const [openCharacter, setOpenCharacter] = useState<Character | null>(null)
  const [error, setError] = useState<string | null>(null)

  const logOut = useCallback(() => {
    localStorage.removeItem(TOKEN_STORAGE_KEY)
    setToken(null)
    setEmail(null)
    setCharacters([])
    setOpenCharacter(null)
  }, [])

  const refresh = useCallback(
    async (activeToken: string) => {
      try {
        const [user, list] = await Promise.all([
          api.me(activeToken),
          api.listCharacters(activeToken),
        ])
        setEmail(user.email)
        setCharacters(list)
      } catch (caught) {
        // A stored token that the backend rejects is worse than no token:
        // it leaves the app stuck on an empty screen with no way back.
        if (caught instanceof ApiError) logOut()
        else setError('Сервер недоступен')
      }
    },
    [logOut],
  )

  useEffect(() => {
    if (token) void refresh(token)
  }, [token, refresh])

  function handleLoggedIn(newToken: string) {
    localStorage.setItem(TOKEN_STORAGE_KEY, newToken)
    setToken(newToken)
  }

  async function handleCreate(name: string, ruleset: string) {
    if (!token) return
    const created = await api.createCharacter(token, { name, ruleset })
    setCharacters((current) => [...current, created])
    setOpenCharacter(created)
  }

  async function handleSave(payload: CharacterUpdate) {
    if (!token || !openCharacter) return
    const updated = await api.updateCharacter(token, openCharacter.id, payload)
    setCharacters((current) => current.map((c) => (c.id === updated.id ? updated : c)))
    setOpenCharacter(updated)
  }

  /** Applies an assistant proposal the player confirmed in the chat. */
  async function handleApplyChanges(characterId: number, patch: CharacterUpdate) {
    if (!token) return
    const updated = await api.updateCharacter(token, characterId, patch)
    setCharacters((current) => current.map((c) => (c.id === updated.id ? updated : c)))
    setOpenCharacter((current) => (current?.id === updated.id ? updated : current))
  }

  async function handleDelete() {
    if (!token || !openCharacter) return
    await api.deleteCharacter(token, openCharacter.id)
    setCharacters((current) => current.filter((c) => c.id !== openCharacter.id))
    setOpenCharacter(null)
  }

  if (!token) return <AuthPanel onLoggedIn={handleLoggedIn} />

  const Sheet = openCharacter ? rulesetById(openCharacter.ruleset)?.Sheet : undefined

  return (
    <div className="mx-auto max-w-7xl px-4 py-6">
      <header className="mb-6 flex flex-wrap items-center gap-3">
        <h1 className="font-heading text-3xl">TAPA</h1>
        <span className="text-sm text-muted-foreground">Ассистент за игровым столом</span>
        <div className="ml-auto flex items-center gap-3">
          {email && <span className="text-sm text-muted-foreground">{email}</span>}
          <Button variant="outline" size="sm" onClick={logOut}>
            Выйти
          </Button>
        </div>
      </header>

      {error && <p className="mb-4 text-sm text-destructive">{error}</p>}

      <Tabs defaultValue="characters">
        <TabsList>
          <TabsTrigger value="characters">Персонажи</TabsTrigger>
          <TabsTrigger value="chat">Чат</TabsTrigger>
        </TabsList>

        <TabsContent value="characters" className="mt-4">
          {openCharacter ? (
            Sheet ? (
              <Sheet
                key={openCharacter.id}
                character={openCharacter}
                onSave={handleSave}
                onDelete={handleDelete}
                onBack={() => setOpenCharacter(null)}
              />
            ) : (
              <div className="space-y-3">
                <Button variant="ghost" onClick={() => setOpenCharacter(null)}>
                  ← К списку
                </Button>
                <p className="text-sm text-destructive">
                  Лист для системы «{rulesetLabel(openCharacter.ruleset)}» пока не реализован.
                </p>
              </div>
            )
          ) : (
            <CharacterList
              characters={characters}
              onOpen={setOpenCharacter}
              onCreate={handleCreate}
            />
          )}
        </TabsContent>

        {/* keepMounted: switching to the sheet must not tear down the chat —
            otherwise a question in flight is lost and the thread resets. */}
        <TabsContent value="chat" className="mt-4" keepMounted>
          <ChatPanel token={token} characters={characters} onApplyChanges={handleApplyChanges} />
        </TabsContent>
      </Tabs>
    </div>
  )
}

export default App
