import { Check, SendHorizontal, Trash2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import {
  api,
  ApiError,
  buildPatchFromChanges,
  type AskSource,
  type Character,
  type CharacterUpdate,
  type ProposedChange,
} from '@/lib/api'
import { cn } from '@/lib/utils'

const STORAGE_KEY = 'tapa.chat.history'

interface Message {
  id: string
  role: 'user' | 'assistant'
  text: string
  sources?: AskSource[]
  /** Which character the question was asked for, if any. */
  characterName?: string
  characterId?: number
  failed?: boolean
  /** Sheet edits the assistant suggested; applied only on confirmation. */
  changes?: ProposedChange[]
  rejected?: string[]
  applied?: boolean
  /** Still arriving — drives the caret and keeps the input disabled. */
  streaming?: boolean
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
  onApplyChanges: (characterId: number, patch: CharacterUpdate) => Promise<void>
}

export function ChatPanel({ token, characters, onApplyChanges }: Props) {
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

    // The reply is placed immediately and filled in as tokens arrive, so the
    // wait shows progress instead of a spinner.
    const replyId = newId()
    setMessages((current) => [
      ...current,
      {
        id: replyId,
        role: 'assistant',
        text: '',
        characterId: characterId ?? undefined,
        streaming: true,
      },
    ])

    const patchReply = (patch: Partial<Message>) =>
      setMessages((current) =>
        current.map((entry) => (entry.id === replyId ? { ...entry, ...patch } : entry)),
      )

    try {
      let streamed = ''
      await api.askStream(token, text, characterId ?? undefined, {
        onSources: (sources) => patchReply({ sources }),
        onDelta: (piece) => {
          streamed += piece
          patchReply({ text: streamed })
        },
        onDone: (result) =>
          patchReply({
            changes: result.proposed_changes,
            rejected: result.rejected_changes,
            streaming: false,
          }),
      })
      patchReply({ streaming: false })
    } catch (caught) {
      patchReply({
        text: caught instanceof ApiError ? caught.message : 'Сервер недоступен',
        failed: true,
        streaming: false,
      })
    } finally {
      setAsking(false)
    }
  }

  async function applyChanges(message: Message) {
    if (!message.characterId || !message.changes?.length) return
    const target = characters.find((entry) => entry.id === message.characterId)
    if (!target) return

    await onApplyChanges(message.characterId, buildPatchFromChanges(target, message.changes))
    setMessages((current) =>
      current.map((entry) => (entry.id === message.id ? { ...entry, applied: true } : entry)),
    )
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
            <p className="font-heading text-xl">Спроси про правила</p>
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
              {message.text && (
                <p className="whitespace-pre-wrap text-sm leading-relaxed">
                  {message.text}
                  {message.streaming && (
                    <span className="ml-0.5 inline-block h-4 w-[2px] animate-pulse bg-current align-text-bottom" />
                  )}
                </p>
              )}
              {!message.text && (
                <p className="text-xs text-muted-foreground">
                  {message.streaming
                    ? message.sources?.length
                      ? 'Нашёл источники, пишу ответ…'
                      : 'Ищу в правилах…'
                    : // A model may answer a sheet request purely with a tool
                      // call and no prose; an empty bubble would look broken.
                      message.changes?.length
                      ? 'Предлагаю изменить лист:'
                      : 'Ответ пустой.'}
                </p>
              )}

              {message.changes && message.changes.length > 0 && (
                <div className="space-y-2 border-t pt-2">
                  <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                    Предлагаемые изменения листа
                  </p>
                  <ul className="space-y-1 text-xs">
                    {message.changes.map((change) => (
                      <li key={change.path} className="flex flex-wrap items-baseline gap-1.5">
                        <span className="font-medium">{change.label || change.path}</span>
                        <span className="font-sans tabular-nums text-muted-foreground">
                          {String(change.before)} → {String(change.value)}
                        </span>
                        {change.reason && (
                          <span className="text-muted-foreground">· {change.reason}</span>
                        )}
                      </li>
                    ))}
                  </ul>
                  {message.applied ? (
                    <p className="text-xs text-muted-foreground">Применено к листу.</p>
                  ) : (
                    <Button size="sm" onClick={() => void applyChanges(message)}>
                      <Check className="size-3.5" />
                      Применить к листу
                    </Button>
                  )}
                </div>
              )}

              {message.rejected && message.rejected.length > 0 && (
                <div className="space-y-1 border-t pt-2">
                  <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                    Отклонено проверкой
                  </p>
                  <ul className="space-y-0.5 text-xs text-muted-foreground">
                    {message.rejected.map((reason) => (
                      <li key={reason}>{reason}</li>
                    ))}
                  </ul>
                </div>
              )}

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
