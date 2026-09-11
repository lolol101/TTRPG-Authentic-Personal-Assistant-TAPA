import { Check, Pencil, Plus, Trash2, X } from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { Chat } from '@/lib/api'
import { cn } from '@/lib/utils'

interface Props {
  chats: Chat[]
  activeId: number | null
  onSelect: (id: number) => void
  onCreate: () => void
  onRename: (id: number, title: string) => void
  onDelete: (id: number) => void
}

export function ChatSidebar({ chats, activeId, onSelect, onCreate, onRename, onDelete }: Props) {
  const [editingId, setEditingId] = useState<number | null>(null)
  const [draft, setDraft] = useState('')

  function startEditing(chat: Chat) {
    setEditingId(chat.id)
    setDraft(chat.title)
  }

  function commit(id: number) {
    const title = draft.trim()
    if (title) onRename(id, title)
    setEditingId(null)
  }

  return (
    <div className="flex w-56 shrink-0 flex-col gap-2">
      <Button variant="outline" size="sm" onClick={onCreate}>
        <Plus className="size-3.5" />
        Новый чат
      </Button>

      <div className="flex-1 space-y-1 overflow-y-auto">
        {chats.length === 0 && (
          <p className="px-1 py-2 text-xs text-muted-foreground">
            Пока ни одного чата. Задай вопрос — он заведётся сам.
          </p>
        )}

        {chats.map((chat) => (
          <div
            key={chat.id}
            className={cn(
              'group flex items-center gap-1 rounded border px-2 py-1.5 text-xs',
              chat.id === activeId ? 'border-secondary bg-secondary/40' : 'hover:bg-muted',
            )}
          >
            {editingId === chat.id ? (
              <>
                <Input
                  autoFocus
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') commit(chat.id)
                    if (event.key === 'Escape') setEditingId(null)
                  }}
                  className="h-6 px-1 text-xs"
                />
                <button type="button" onClick={() => commit(chat.id)} title="Сохранить">
                  <Check className="size-3.5" />
                </button>
                <button type="button" onClick={() => setEditingId(null)} title="Отмена">
                  <X className="size-3.5" />
                </button>
              </>
            ) : (
              <>
                <button
                  type="button"
                  onClick={() => onSelect(chat.id)}
                  className="flex-1 truncate text-left"
                  title={chat.title || 'Без названия'}
                >
                  {chat.title || 'Без названия'}
                </button>
                <span className="tabular-nums text-[10px] text-muted-foreground">
                  {chat.message_count}
                </span>
                {/* Kept out of the way until the row is hovered: the list is
                    for choosing a chat, not for managing one. */}
                <button
                  type="button"
                  onClick={() => startEditing(chat)}
                  className="opacity-0 transition-opacity group-hover:opacity-60 hover:!opacity-100"
                  title="Переименовать"
                >
                  <Pencil className="size-3" />
                </button>
                <button
                  type="button"
                  onClick={() => onDelete(chat.id)}
                  className="opacity-0 transition-opacity group-hover:opacity-60 hover:!opacity-100"
                  title="Удалить чат"
                >
                  <Trash2 className="size-3" />
                </button>
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
