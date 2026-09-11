import { Check, SendHorizontal } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { ChatSidebar } from '@/components/ChatSidebar'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import {
  api,
  ApiError,
  buildPatchFromChanges,
  type AskMemory,
  type AskSource,
  type Chat,
  type Character,
  type CharacterUpdate,
  type ProposedChange,
} from '@/lib/api'
import { cn } from '@/lib/utils'
import { DEFAULT_RULESET, QUESTION_RULESETS, rulesetLabel } from '@/rulesets/registry'

interface Message {
  id: string
  /** Set once the turn is stored; absent while it is still being streamed. */
  serverId?: number
  role: 'user' | 'assistant'
  text: string
  sources?: AskSource[]
  changes?: ProposedChange[]
  rejected?: string[]
  applied?: boolean
  failed?: boolean
  /** Still arriving — drives the caret and keeps the input disabled. */
  streaming?: boolean
}

/** Where the model's memory of this chat begins, as the last answer saw it. */
interface MemoryMark extends AskMemory {
  /** Index of the first message that still fit inside the budget. */
  boundary: number
}

function newId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function toMessage(stored: {
  id: number
  role: 'user' | 'assistant'
  text: string
  sources: AskSource[]
  proposed_changes: ProposedChange[]
  rejected_changes: string[]
  applied: boolean
}): Message {
  return {
    id: String(stored.id),
    serverId: stored.id,
    role: stored.role,
    text: stored.text,
    sources: stored.sources,
    changes: stored.proposed_changes,
    rejected: stored.rejected_changes,
    applied: stored.applied,
  }
}

interface Props {
  token: string
  characters: Character[]
  onApplyChanges: (characterId: number, patch: CharacterUpdate) => Promise<void>
}

export function ChatPanel({ token, characters, onApplyChanges }: Props) {
  const [chats, setChats] = useState<Chat[]>([])
  const [activeId, setActiveId] = useState<number | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [memory, setMemory] = useState<MemoryMark | null>(null)
  const [question, setQuestion] = useState('')
  const [asking, setAsking] = useState(false)
  const [error, setError] = useState('')

  // Used only until a chat exists: the first question creates one, and these
  // are what it is created with.
  const [draftCharacterId, setDraftCharacterId] = useState<number | null>(null)
  const [draftRuleset, setDraftRuleset] = useState<string>(DEFAULT_RULESET)

  const endRef = useRef<HTMLDivElement>(null)

  const activeChat = chats.find((chat) => chat.id === activeId) ?? null
  const characterId = activeChat ? activeChat.character_id : draftCharacterId
  const ruleset = activeChat ? activeChat.ruleset : draftRuleset
  const character = characters.find((entry) => entry.id === characterId) ?? null

  const refreshChats = useCallback(async () => {
    const listed = await api.listChats(token)
    setChats(listed)
    return listed
  }, [token])

  useEffect(() => {
    void refreshChats()
      .then((listed) => setActiveId((current) => current ?? listed[0]?.id ?? null))
      .catch(() => setError('Не удалось загрузить список чатов'))
  }, [refreshChats])

  useEffect(() => {
    if (activeId === null) {
      setMessages([])
      return
    }
    // The mark belongs to the chat that produced it; carrying it across would
    // draw the line in an arbitrary place.
    setMemory(null)
    void api
      .listMessages(token, activeId)
      .then((stored) => setMessages(stored.map(toMessage)))
      .catch(() => setError('Не удалось загрузить сообщения'))
  }, [token, activeId])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function createChat(): Promise<Chat> {
    const chat = await api.createChat(token, {
      character_id: draftCharacterId,
      ruleset: draftRuleset,
    })
    setChats((current) => [chat, ...current])
    setActiveId(chat.id)
    setMessages([])
    return chat
  }

  async function patchActiveChat(patch: Parameters<typeof api.updateChat>[2]) {
    if (!activeChat) return
    const updated = await api.updateChat(token, activeChat.id, patch)
    setChats((current) => current.map((chat) => (chat.id === updated.id ? updated : chat)))
  }

  function chooseCharacter(id: number | null) {
    if (activeChat) void patchActiveChat({ character_id: id })
    else setDraftCharacterId(id)
  }

  function chooseRuleset(id: string) {
    if (activeChat) void patchActiveChat({ ruleset: id })
    else setDraftRuleset(id)
  }

  async function send() {
    const text = question.trim()
    if (!text || asking) return

    setError('')
    setAsking(true)

    let chat = activeChat
    try {
      if (!chat) chat = await createChat()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Не удалось создать чат')
      setAsking(false)
      return
    }

    // How much of the chat existed before this question — the answer reports
    // how many of these turns fit, which is where the memory line goes.
    const before = messages.length

    setQuestion('')
    setMessages((current) => [...current, { id: newId(), role: 'user', text }])

    // The reply is placed immediately and filled in as tokens arrive, so the
    // wait shows progress instead of a spinner.
    const replyId = newId()
    setMessages((current) => [
      ...current,
      { id: replyId, role: 'assistant', text: '', streaming: true },
    ])

    const patchReply = (patch: Partial<Message>) =>
      setMessages((current) =>
        current.map((entry) => (entry.id === replyId ? { ...entry, ...patch } : entry)),
      )

    try {
      let streamed = ''
      await api.askStream(
        token,
        { question: text, chatId: chat.id },
        {
          onSources: (sources) => patchReply({ sources }),
          onDelta: (piece) => {
            streamed += piece
            patchReply({ text: streamed })
          },
          onDone: (result) => {
            patchReply({
              changes: result.proposed_changes,
              rejected: result.rejected_changes,
              serverId: result.message_id ?? undefined,
              streaming: false,
            })
            if (result.memory) {
              setMemory({ ...result.memory, boundary: before - result.memory.used })
            }
          },
        },
      )
      patchReply({ streaming: false })
      void refreshChats()
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
    if (!character || !message.changes?.length) return

    await onApplyChanges(character.id, buildPatchFromChanges(character, message.changes))
    if (activeChat && message.serverId) {
      await api.markApplied(token, activeChat.id, message.serverId)
    }
    setMessages((current) =>
      current.map((entry) => (entry.id === message.id ? { ...entry, applied: true } : entry)),
    )
  }

  async function removeChat(id: number) {
    await api.deleteChat(token, id)
    const remaining = chats.filter((chat) => chat.id !== id)
    setChats(remaining)
    if (id === activeId) setActiveId(remaining[0]?.id ?? null)
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends, Shift+Enter breaks the line — the usual chat contract.
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void send()
    }
  }

  return (
    <div className="flex h-[calc(100svh-11rem)] gap-3">
      <ChatSidebar
        chats={chats}
        activeId={activeId}
        onSelect={setActiveId}
        onCreate={() => void createChat()}
        onRename={(id, title) => {
          void api
            .updateChat(token, id, { title })
            .then((updated) =>
              setChats((current) =>
                current.map((chat) => (chat.id === updated.id ? updated : chat)),
              ),
            )
        }}
        onDelete={(id) => void removeChat(id)}
      />

      <div className="flex min-w-0 flex-1 flex-col gap-3">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
            Спросить за
          </span>
          <button
            type="button"
            onClick={() => chooseCharacter(null)}
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
              onClick={() => chooseCharacter(entry.id)}
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
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
            По правилам
          </span>
          {QUESTION_RULESETS.map((entry) => (
            <button
              key={entry.id}
              type="button"
              disabled={character !== null}
              onClick={() => chooseRuleset(entry.id)}
              title={
                character
                  ? `Систему задаёт выбранный персонаж (${rulesetLabel(character.ruleset)})`
                  : undefined
              }
              className={cn(
                'rounded border px-2.5 py-1 text-xs transition-colors disabled:opacity-40',
                (character ? character.ruleset : ruleset) === entry.id
                  ? 'border-secondary bg-secondary text-secondary-foreground'
                  : 'hover:bg-muted',
              )}
            >
              {entry.label}
            </button>
          ))}
        </div>

        {error && <p className="text-xs text-destructive">{error}</p>}

        <div className="flex-1 space-y-3 overflow-y-auto rounded-md border bg-card/40 p-3">
          {messages.length === 0 && (
            <div className="flex h-full flex-col items-center justify-center gap-1 text-center">
              <p className="font-heading text-xl">Спроси про правила</p>
              <p className="max-w-md text-sm text-muted-foreground">
                Ответ строится только по проиндексированным правилам. Выбери персонажа, и его лист
                уйдёт в вопрос — а чат запомнит этот выбор.
              </p>
            </div>
          )}

          {messages.map((message, index) => (
            <div key={message.id}>
              {memory !== null && memory.dropped > 0 && index === memory.boundary && (
                <div className="mb-3 flex items-center gap-2">
                  <div className="h-px flex-1 bg-border" />
                  <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                    выше модель уже не помнит · {memory.dropped}{' '}
                    {memory.dropped === 1 ? 'сообщение' : 'сообщений'}
                  </span>
                  <div className="h-px flex-1 bg-border" />
                </div>
              )}

              <div className={cn('flex', message.role === 'user' ? 'justify-end' : 'justify-start')}>
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
          <Button
            onClick={() => void send()}
            disabled={asking || !question.trim()}
            className="h-16"
          >
            <SendHorizontal className="size-4" />
          </Button>
        </div>

        <p className="text-[10px] text-muted-foreground">
          {memory ? (
            <>
              Модель помнит последние {memory.used}{' '}
              {memory.used === 1 ? 'сообщение' : 'сообщений'} — {memory.tokens} из {memory.budget}{' '}
              токенов контекста
              {memory.dropped > 0 && `, ещё ${memory.dropped} за границей памяти`}.
            </>
          ) : (
            'История чата уходит в модель вместе с вопросом, пока помещается в окно контекста.'
          )}
        </p>
      </div>
    </div>
  )
}
