import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import { api, ApiError, type AskResponse, type Character } from '@/lib/api'

interface Props {
  token: string
  characters: Character[]
}

export function AskPanel({ token, characters }: Props) {
  const [question, setQuestion] = useState('')
  const [characterId, setCharacterId] = useState<number | null>(null)
  const [result, setResult] = useState<AskResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [asking, setAsking] = useState(false)

  async function handleAsk(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setResult(null)
    setAsking(true)
    try {
      setResult(await api.ask(token, question, characterId ?? undefined))
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Сервер недоступен')
    } finally {
      setAsking(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="font-heading heading-marked text-2xl font-normal">
          Вопрос по правилам
        </CardTitle>
        <CardDescription>
          Ответ строится только по проиндексированным правилам PF2e — сейчас это раздел действий с
          pf2.ru.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {characters.length > 0 && (
          <div className="space-y-1.5">
            <p className="text-[11px] uppercase tracking-wide text-muted-foreground">
              Спросить за персонажа
            </p>
            <div className="flex flex-wrap gap-1.5">
              <button
                type="button"
                onClick={() => setCharacterId(null)}
                className={cn(
                  'rounded border px-2.5 py-1 text-xs transition-colors',
                  characterId === null
                    ? 'border-secondary bg-secondary text-secondary-foreground'
                    : 'hover:bg-muted',
                )}
              >
                Без персонажа
              </button>
              {characters.map((character) => (
                <button
                  key={character.id}
                  type="button"
                  onClick={() => setCharacterId(character.id)}
                  className={cn(
                    'rounded border px-2.5 py-1 text-xs transition-colors',
                    characterId === character.id
                      ? 'border-secondary bg-secondary text-secondary-foreground'
                      : 'hover:bg-muted',
                  )}
                >
                  {character.name}
                </button>
              ))}
            </div>
            {characterId !== null && (
              <p className="text-xs text-muted-foreground">
                Лист уйдёт в запрос с уже посчитанными модификаторами. Имя игрока и личные
                заметки не отправляются.
              </p>
            )}
          </div>
        )}

        <form onSubmit={handleAsk} className="space-y-3">
          <Textarea
            rows={3}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Что делает действие Захват?"
            required
          />
          <Button type="submit" disabled={asking}>
            {asking ? 'Спрашиваю…' : 'Спросить'}
          </Button>
        </form>

        {error && <p className="text-sm text-destructive">{error}</p>}

        {result && (
          <div className="space-y-3">
            <Separator />
            <p className="whitespace-pre-wrap text-sm leading-relaxed">{result.answer}</p>
            {result.sources.length > 0 && (
              <div className="space-y-1">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Источники
                </p>
                <ul className="space-y-1 text-sm">
                  {result.sources.map((source) => (
                    <li key={source.url}>
                      <a
                        href={source.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-primary underline-offset-4 hover:underline"
                      >
                        {source.title}
                      </a>
                      {source.source_book && (
                        <span className="text-muted-foreground"> — {source.source_book}</span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
