import { SendHorizontal } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { ChatSidebar } from '@/components/ChatSidebar'
import { ProposedChanges } from '@/components/ProposedChanges'
import { SourcesPopover } from '@/components/SourcesPopover'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import {
  api,
  ApiError,
  buildPatchFromChanges,
  type AskMemory,
  type AskSource,
  type AskStage,
  type Chat,
  type Clarification,
  type Character,
  type CharacterUpdate,
  type ProposedChange,
} from '@/lib/api'
import { cn } from '@/lib/utils'
import { DEFAULT_RULESET, QUESTION_RULESETS, rulesetLabel } from '@/rulesets/registry'

/**
 * Whether the "Отклонено проверкой" list should start collapsed.
 *
 * An unresolved rejection needs the player's eye — it stays open. One the
 * player has already acted on (applied the whole turn, or even one of its
 * sections) does not need to keep reading as an open conflict, so it folds
 * away; the record itself is never dropped.
 */
export function rejectedStartsCollapsed(
  applied: boolean | undefined,
  appliedSections: string[] | undefined,
): boolean {
  return Boolean(applied) || (appliedSections?.length ?? 0) > 0
}

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
  /** Sections already written to the sheet, when applied a part at a time. */
  appliedSections?: string[]
  /** Asked instead of proposing an edit; answering it continues the turn. */
  clarification?: Clarification
  failed?: boolean
  /** Still arriving — drives the caret and keeps the input disabled. */
  streaming?: boolean
  /** What the server is doing right now, while there is no answer to show. */
  stage?: AskStage
}

/** Sheet areas as the player's own sheet names them. */
const AREA_LABELS: Record<string, string> = {
  ancestry: 'происхождению',
  background: 'предыстории',
  class: 'классу',
  skills: 'навыкам',
  feats: 'чертам',
  equipment: 'снаряжению',
  spells: 'заклинаниям',
  bio: 'биографии',
}

/**
 * What to show while the answer does not exist yet.
 *
 * A split sheet request runs a planning call and then one search per area,
 * which is many seconds on a slow provider. Naming the area and counting the
 * steps turns that wait into something with a visible end.
 */
function stageLabel(stage: AskStage | undefined, hasSources: boolean): string {
  if (!stage) return hasSources ? 'Пишу ответ…' : 'Ищу в правилах…'
  if (stage.stage === 'rewriting') return 'Перевожу вопрос на язык правил…'
  if (stage.stage === 'planning') return 'Разбираю запрос по разделам листа…'
  if (stage.stage === 'generating') return 'Пишу ответ…'

  const area = stage.area ? AREA_LABELS[stage.area] ?? stage.area : ''
  if (area && stage.index && stage.total) {
    return `Ищу правила по ${area} — ${stage.index} из ${stage.total}…`
  }
  return 'Ищу в правилах…'
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
  /** `${messageId}:${section}` for every apply request still in flight — the
   * button greys out the instant it's clicked, not once the network answers. */
  const [applying, setApplying] = useState<Set<string>>(new Set())

  // Used only until a chat exists: the first question creates one, and these
  // are what it is created with.
  const [draftCharacterId, setDraftCharacterId] = useState<number | null>(null)
  const [draftRuleset, setDraftRuleset] = useState<string>(DEFAULT_RULESET)

  const endRef = useRef<HTMLDivElement>(null)
  /** Which chat the messages in state belong to, so they are not re-fetched. */
  const loadedFor = useRef<number | null>(null)

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
      loadedFor.current = null
      return
    }
    // Already holding this chat's messages. Re-fetching would race the turn
    // being typed into a chat created a moment ago: the server has none yet,
    // and the empty answer would land last and wipe the question off screen.
    if (loadedFor.current === activeId) return

    // The mark belongs to the chat that produced it; carrying it across would
    // draw the line in an arbitrary place.
    setMemory(null)

    let cancelled = false
    void api
      .listMessages(token, activeId)
      .then((stored) => {
        if (cancelled) return
        setMessages(stored.map(toMessage))
        loadedFor.current = activeId
      })
      .catch(() => {
        if (!cancelled) setError('Не удалось загрузить сообщения')
      })

    // Switching chats faster than the network answers would otherwise show
    // the previous chat's messages under the current chat's name.
    return () => {
      cancelled = true
    }
  }, [token, activeId])

  // A new turn or a growing answer is worth following; applying a change is
  // not — it only rewrites a message in place, and scrolling away from the
  // button just clicked hides the very thing that changed.
  const streamedText = messages[messages.length - 1]?.streaming
    ? messages[messages.length - 1]?.text
    : null

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length, streamedText])

  async function createChat(): Promise<Chat> {
    const chat = await api.createChat(token, {
      character_id: draftCharacterId,
      ruleset: draftRuleset,
    })
    setChats((current) => [chat, ...current])
    // Marked before the id changes: a chat created here is empty by
    // definition, so the effect must not go asking the server about it.
    loadedFor.current = chat.id
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

  async function send(override?: string) {
    const text = (override ?? question).trim()
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
          onStage: (stage) => patchReply({ stage }),
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
              clarification: result.clarification ?? undefined,
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

  /** Sends a chosen option straight back, so the turn continues in one click. */
  async function answerClarification(option: string) {
    if (asking) return
    setQuestion(option)
    await send(option)
  }

  async function applyChanges(
    message: Message,
    section: string,
    entries: ProposedChange[],
  ) {
    if (!character || !entries.length) return

    const key = `${message.id}:${section}`
    setApplying((current) => new Set(current).add(key))
    try {
      await onApplyChanges(character.id, buildPatchFromChanges(character, entries))

      const sections = new Set(message.appliedSections ?? [])
      if (section === '*')
        (message.changes ?? []).forEach((c) => sections.add(c.section ?? 'Основное'))
      else sections.add(section)

      // The turn is marked applied once nothing is left — but every section
      // reports its paths as it goes, so a player who takes half the advice
      // is counted as having taken half, not as having refused it all.
      const remaining = (message.changes ?? []).some(
        (change) => !sections.has(change.section ?? 'Основное'),
      )
      if (activeChat && message.serverId) {
        await api.markApplied(token, activeChat.id, message.serverId, {
          applied: !remaining,
          paths: entries.map((entry) => entry.path),
        })
      }

      setMessages((current) =>
        current.map((entry) =>
          entry.id === message.id
            ? { ...entry, appliedSections: [...sections], applied: !remaining }
            : entry,
        ),
      )
    } finally {
      setApplying((current) => {
        const next = new Set(current)
        next.delete(key)
        return next
      })
    }
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
                    <p className="flex items-center gap-2 text-xs text-muted-foreground">
                      {message.streaming && (
                        <span className="inline-block size-1.5 shrink-0 animate-pulse rounded-full bg-current" />
                      )}
                      {message.streaming
                        ? stageLabel(message.stage, Boolean(message.sources?.length))
                        : // A model may answer a sheet request purely with a tool
                          // call and no prose; an empty bubble would look broken.
                          message.changes?.length
                          ? 'Предлагаю изменить лист:'
                          : 'Ответ пустой.'}
                    </p>
                  )}

                  {message.changes && message.changes.length > 0 && (
                    <ProposedChanges
                      changes={message.changes}
                      appliedSections={
                        message.applied ? ['*'] : (message.appliedSections ?? [])
                      }
                      applyingSections={[...applying]
                        .filter((key) => key.startsWith(`${message.id}:`))
                        .map((key) => key.slice(message.id.length + 1))}
                      onApply={(section, entries) =>
                        void applyChanges(message, section, entries)
                      }
                    />
                  )}

                  {message.clarification && (
                <div className="space-y-2 border-t pt-2">
                  <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                    Уточнение перед правкой
                  </p>
                  <p className="text-sm">{message.clarification.question}</p>
                  {message.clarification.options.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {message.clarification.options.map((option) => (
                        <button
                          key={option}
                          type="button"
                          disabled={asking}
                          onClick={() => void answerClarification(option)}
                          className="rounded border px-2.5 py-1 text-xs transition-colors hover:bg-muted disabled:opacity-40"
                        >
                          {option}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {message.rejected && message.rejected.length > 0 && (
                    // Rejected reasons stay in the record — dropping them
                    // once something is applied would hide that the check
                    // ever disagreed. Collapsed instead: an unresolved
                    // rejection needs the player's eye, one already acted on
                    // does not need to keep reading as an open conflict.
                    <details
                      className="space-y-1 border-t pt-2"
                      open={!rejectedStartsCollapsed(message.applied, message.appliedSections)}
                    >
                      <summary className="cursor-pointer text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                        Отклонено проверкой ({message.rejected.length})
                      </summary>
                      <ul className="mt-1 space-y-0.5 text-xs text-muted-foreground">
                        {message.rejected.map((reason) => (
                          <li key={reason}>{reason}</li>
                        ))}
                      </ul>
                    </details>
                  )}

                  {message.sources && message.sources.length > 0 && (
                    <SourcesPopover sources={message.sources} />
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
