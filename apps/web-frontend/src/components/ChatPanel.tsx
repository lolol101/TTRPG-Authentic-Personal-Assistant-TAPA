import { SendHorizontal, Trash2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { api, ApiError, type AskSource, type Character } from '@/lib/api'
import { cn } from '@/lib/utils'

const STORAGE_KEY = 'tapa.chat.history'

interface Message {
  id: string
  role: 'user' | 'assistant'
  text: string
  sources?: AskSource[]
  /** Which character the question was asked for, if any. */
  characterName?: string
  failed?: boolean
}

function loadHistory(): Message[] {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    return stored ? (JSON.parse(stored) as Message[]) : []
  } catch {
    return []
  }
}

function saveHistory(messages: Message[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(messages))
  } catch {
    // History is a convenience; losing it must not break sending.
  }
}

function newId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

interface Props {
  token: string
  characters: Character[]
}

export function ChatPanel({ token, characters }: Props) {
  const [messages, setMessages] = useState<Message[]>(loadHistory)
  const [question, setQuestion] = useState('')
  const [characterId, setCharacterId] = useState<number | null>(null)
  const [asking, setAsking] = useState(false)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    saveHistory(messages)
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const character = characters.find((entry) => entry.id === characterId) ?? null

  async function send() {
    const text = question.trim()
    if (!text || asking) return

    setMessages((current) => [
      ...current,
      { id: newId(), role: 'user', text, characterName: character?.name },
    ])
    setQuestion('')
    setAsking(true)

    try {
      const answer = await api.ask(token, text, characterId ?? undefined)
      setMessages((current) => [
        ...current,
        { id: newId(), role: 'assistant', text: answer.answer, sources: answer.sources },
      ])
    } catch (caught) {
      setMessages((current) => [
        ...current,
        {
          id: newId(),
          role: 'assistant',
          text: caught instanceof ApiError ? caught.message : 'Сервер недоступен',
          failed: true,
        },
      ])
    } finally {
      setAsking(false)
    }
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends, Shift+Enter breaks the line — the usual chat contract.
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void send()
    }
  }

  return (
    <div className="flex h-[calc(100svh-11rem)] flex-col gap-3">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
          Спросить за
        </span>
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
        {characters.map((entry) => (
          <button
            key={entry.id}
            type="button"
            onClick={() => setCharacterId(entry.id)}
            className={cn(
              'rounded border px-2.5 py-1 text-xs transition-colors',
              characterId === entry.id
                ? 'border-secondary bg-secondary text-secondary-foreground'
                : 'hover:bg-muted',
            )}
          >
            {entry.name}
          </button>
        ))}
        {messages.length > 0 && (
          <Button
            variant="ghost"
            size="sm"
            className="ml-auto"
            onClick={() => setMessages([])}
            title="Очистить историю"
          >
            <Trash2 className="size-3.5" />
            Очистить
          </Button>
        )}
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto rounded-md border bg-card/40 p-3">
        {messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center gap-1 text-center">
            <p className="font-heading text-2xl">Спроси про правила</p>
            <p className="max-w-md text-sm text-muted-foreground">
              Ответ строится только по проиндексированным правилам PF2e — сейчас это раздел
              действий с pf2.ru. Выбери персонажа, и его лист уйдёт в вопрос.
            </p>
          </div>
        )}

        {messages.map((message) => (
          <div
            key={message.id}
            className={cn('flex', message.role === 'user' ? 'justify-end' : 'justify-start')}
          >
            <div
              className={cn(
                'max-w-[85%] space-y-2 rounded-lg px-3 py-2',
                message.role === 'user'
                  ? 'bg-secondary text-secondary-foreground'
                  : message.failed
                    ? 'border border-destructive/40 bg-destructive/10'
                    : 'border bg-card',
              )}
            >
              {message.characterName && (
                <p className="text-[10px] uppercase tracking-wide opacity-70">
                  за {message.characterName}
                </p>
              )}
              <p className="whitespace-pre-wrap text-sm leading-relaxed">{message.text}</p>

              {message.sources && message.sources.length > 0 && (
                <div className="space-y-1 border-t pt-2">
                  <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                    Источники
                  </p>
                  <ul className="space-y-0.5 text-xs">
                    {message.sources.map((source) => (
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
          </div>
        ))}

        {asking && (
          <div className="flex justify-start">
            <div className="rounded-lg border bg-card px-3 py-2 text-sm text-muted-foreground">
              Ищу в правилах…
            </div>
          </div>
        )}

        <div ref={endRef} />
      </div>

      <div className="flex items-end gap-2">
        <Textarea
          rows={2}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Что делает действие Захват?"
          className="resize-none"
        />
        <Button onClick={() => void send()} disabled={asking || !question.trim()} className="h-16">
          <SendHorizontal className="size-4" />
        </Button>
      </div>
      <p className="text-[10px] text-muted-foreground">
        История хранится в этом браузере. Диалог не передаётся модели как контекст — каждый вопрос
        отвечается отдельно; серверные чаты с историей есть в бэклоге.
      </p>
    </div>
  )
}
