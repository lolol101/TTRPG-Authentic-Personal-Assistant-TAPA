import { useCallback, useEffect, useState } from 'react'
import { AskPanel } from '@/components/AskPanel'
import { AuthPanel } from '@/components/AuthPanel'
import { CharacterList } from '@/components/CharacterList'
import { CharacterSheet } from '@/components/CharacterSheet'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { api, ApiError, type Character, type CharacterUpdate } from '@/lib/api'

const TOKEN_STORAGE_KEY = 'tapa.token'

function App() {
  const [token, setToken] = useState<string | null>(() =>
    localStorage.getItem(TOKEN_STORAGE_KEY),
  )
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

  async function handleCreate(name: string) {
    if (!token) return
    const created = await api.createCharacter(token, { name })
    setCharacters((current) => [...current, created])
    setOpenCharacter(created)
  }

  async function handleSave(payload: CharacterUpdate) {
    if (!token || !openCharacter) return
    const updated = await api.updateCharacter(token, openCharacter.id, payload)
    setCharacters((current) => current.map((c) => (c.id === updated.id ? updated : c)))
    setOpenCharacter(updated)
  }

  async function handleDelete() {
    if (!token || !openCharacter) return
    await api.deleteCharacter(token, openCharacter.id)
    setCharacters((current) => current.filter((c) => c.id !== openCharacter.id))
    setOpenCharacter(null)
  }

  if (!token) return <AuthPanel onLoggedIn={handleLoggedIn} />

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <header className="mb-6 flex flex-wrap items-center gap-3">
        <h1 className="font-heading text-3xl">TAPA</h1>
        <span className="text-sm text-muted-foreground">Pathfinder 2e</span>
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
          <TabsTrigger value="rules">Правила</TabsTrigger>
        </TabsList>

        <TabsContent value="characters" className="mt-4">
          {openCharacter ? (
            <CharacterSheet
              key={openCharacter.id}
              character={openCharacter}
              onSave={handleSave}
              onDelete={handleDelete}
              onBack={() => setOpenCharacter(null)}
            />
          ) : (
            <CharacterList
              characters={characters}
              onOpen={setOpenCharacter}
              onCreate={handleCreate}
            />
          )}
        </TabsContent>

        <TabsContent value="rules" className="mt-4">
          <AskPanel />
        </TabsContent>
      </Tabs>
    </div>
  )
}

export default App
