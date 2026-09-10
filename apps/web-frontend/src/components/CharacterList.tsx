import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import type { Character } from '@/lib/api'

interface Props {
  characters: Character[]
  onOpen: (character: Character) => void
  onCreate: (name: string) => Promise<void>
}

export function CharacterList({ characters, onOpen, onCreate }: Props) {
  const [name, setName] = useState('')
  const [creating, setCreating] = useState(false)

  async function handleCreate(event: React.FormEvent) {
    event.preventDefault()
    if (!name.trim()) return
    setCreating(true)
    try {
      await onCreate(name.trim())
      setName('')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Новый персонаж</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleCreate} className="flex gap-2">
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Имя персонажа"
            />
            <Button type="submit" disabled={creating}>
              {creating ? 'Создаю…' : 'Создать'}
            </Button>
          </form>
        </CardContent>
      </Card>

      {characters.length === 0 ? (
        <p className="text-sm text-muted-foreground">Пока нет персонажей — создай первого.</p>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {characters.map((character) => (
            <Card
              key={character.id}
              className="cursor-pointer transition-colors hover:bg-muted/50"
              onClick={() => onOpen(character)}
            >
              <CardHeader>
                <CardTitle>{character.name}</CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">
                <p>
                  {[character.ancestry, character.class_name].filter(Boolean).join(' · ') ||
                    'Без народа и класса'}
                </p>
                <p className="mt-1">
                  Уровень {character.level} · КБ {character.ac} · ХП {character.hp_current}/
                  {character.hp_max}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
