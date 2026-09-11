import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import type { Character } from '@/lib/api'
import { cn } from '@/lib/utils'
import { DEFAULT_RULESET, RULESETS, rulesetById, rulesetLabel } from '@/rulesets/registry'

interface Props {
  characters: Character[]
  onOpen: (character: Character) => void
  onCreate: (name: string, ruleset: string) => Promise<void>
}

export function CharacterList({ characters, onOpen, onCreate }: Props) {
  const [name, setName] = useState('')
  const [ruleset, setRuleset] = useState(DEFAULT_RULESET)
  const [creating, setCreating] = useState(false)

  async function handleCreate(event: React.FormEvent) {
    event.preventDefault()
    if (!name.trim()) return
    setCreating(true)
    try {
      await onCreate(name.trim(), ruleset)
      setName('')
    } finally {
      setCreating(false)
    }
  }

  const selected = rulesetById(ruleset)

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="font-heading heading-marked text-xl font-normal">
            Новый персонаж
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleCreate} className="space-y-3">
            <div className="space-y-1.5">
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
                Система правил
              </p>
              <div className="flex flex-wrap gap-1.5">
                {RULESETS.map((entry) => (
                  <button
                    key={entry.id}
                    type="button"
                    onClick={() => setRuleset(entry.id)}
                    className={cn(
                      'rounded border px-3 py-1.5 text-sm transition-colors',
                      entry.id === ruleset
                        ? 'border-secondary bg-secondary text-secondary-foreground'
                        : 'hover:bg-muted',
                    )}
                  >
                    {entry.label}
                  </button>
                ))}
              </div>
              {selected && <p className="text-xs text-muted-foreground">{selected.description}</p>}
            </div>

            <div className="flex gap-2">
              <Input
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Имя персонажа"
              />
              <Button type="submit" disabled={creating}>
                {creating ? 'Создаю…' : 'Создать'}
              </Button>
            </div>
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
                <CardTitle className="font-heading text-xl font-normal">
                  {character.name}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-1 text-sm text-muted-foreground">
                <p className="text-[10px] uppercase tracking-wide">
                  {rulesetLabel(character.ruleset)}
                </p>
                <p>
                  {[character.ancestry, character.class_name].filter(Boolean).join(' · ') ||
                    'Без народа и класса'}
                </p>
                <p>
                  Уровень {character.level} · КБ {character.ac} · ПЗ {character.hp_current}/
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
