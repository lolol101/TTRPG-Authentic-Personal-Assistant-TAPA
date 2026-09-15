import { History, Save, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { api, ApiError, type Snapshot } from '@/lib/api'
import { cn } from '@/lib/utils'

interface Props {
  token: string
  characterId: number
  /** Called after a restore so the open sheet stops showing the old numbers. */
  onRestored: () => Promise<void> | void
}

/**
 * Save points for a sheet, kept and chosen by hand.
 *
 * Deliberate rather than automatic: a list the player filled themselves is
 * one they can recognise, where twenty auto-saves named by timestamp are a
 * pile to dig through at the moment they are least able to.
 */
export function SheetVersions({ token, characterId, onRestored }: Props) {
  const [open, setOpen] = useState(false)
  const [snapshots, setSnapshots] = useState<Snapshot[]>([])
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    try {
      setSnapshots(await api.listSnapshots(token, characterId))
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Не удалось загрузить сохранения')
    }
  }, [token, characterId])

  useEffect(() => {
    if (open) void refresh()
  }, [open, refresh])

  async function run(action: () => Promise<unknown>) {
    setBusy(true)
    setError('')
    try {
      await action()
      await refresh()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Не получилось')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="relative">
      <Button variant="outline" onClick={() => setOpen((current) => !current)}>
        <History className="size-4" />
        Версии
      </Button>

      {open && (
        <div className="absolute right-0 z-20 mt-2 w-80 space-y-3 rounded-md border bg-card p-3 shadow-lg">
          <div className="flex gap-2">
            <Input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Название, например «до боя»"
              className="h-8 text-xs"
            />
            <Button
              size="sm"
              disabled={busy}
              onClick={() =>
                void run(async () => {
                  await api.createSnapshot(token, characterId, name)
                  setName('')
                })
              }
            >
              <Save className="size-3.5" />
            </Button>
          </div>
          <p className="text-[10px] text-muted-foreground">
            Сохраняется состояние, записанное на сервере. Не забудь нажать «Сохранить», если
            правил лист прямо сейчас.
          </p>

          {error && <p className="text-xs text-destructive">{error}</p>}

          <div className="max-h-64 space-y-1 overflow-y-auto">
            {snapshots.length === 0 && (
              <p className="py-2 text-center text-xs text-muted-foreground">
                Пока ничего не сохранено.
              </p>
            )}
            {snapshots.map((snapshot) => (
              <div
                key={snapshot.id}
                className={cn(
                  'flex items-center gap-1.5 rounded border px-2 py-1.5 text-xs',
                  'hover:bg-muted',
                )}
              >
                <span className="flex-1 truncate" title={snapshot.name}>
                  {snapshot.name}
                </span>
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={busy}
                  onClick={() =>
                    void run(async () => {
                      await api.restoreSnapshot(token, characterId, snapshot.id)
                      await onRestored()
                      setOpen(false)
                    })
                  }
                >
                  Вернуть
                </Button>
                <button
                  type="button"
                  disabled={busy}
                  title="Удалить сохранение"
                  onClick={() =>
                    void run(() => api.deleteSnapshot(token, characterId, snapshot.id))
                  }
                  className="opacity-60 transition-opacity hover:opacity-100"
                >
                  <Trash2 className="size-3" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
