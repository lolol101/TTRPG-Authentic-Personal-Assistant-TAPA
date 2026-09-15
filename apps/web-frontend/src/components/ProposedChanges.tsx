import { Check } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { ProposedChange } from '@/lib/api'

interface Props {
  changes: ProposedChange[]
  /** Sections already written to the sheet, so they are not offered twice. */
  appliedSections: string[]
  onApply: (section: string, changes: ProposedChange[]) => void
}

/** Cards arrive as a list of objects; their names are what the player reads. */
function describe(value: unknown): string {
  if (Array.isArray(value)) {
    const names = value.map((entry) =>
      entry && typeof entry === 'object' && 'name' in entry
        ? String((entry as { name: unknown }).name)
        : '?',
    )
    return names.join(', ')
  }
  if (value === null || value === undefined) return '—'
  if (typeof value === 'object') return '…'
  return String(value)
}

function groupBySection(changes: ProposedChange[]): [string, ProposedChange[]][] {
  const groups = new Map<string, ProposedChange[]>()
  for (const change of changes) {
    const section = change.section || 'Основное'
    groups.set(section, [...(groups.get(section) ?? []), change])
  }
  return [...groups.entries()]
}

/**
 * Sheet edits, grouped the way the sheet itself is.
 *
 * Filling a character produces dozens of changes at once, and forty lines
 * under a single button is a confirmation nobody reads — which defeats the
 * point of asking. Per-section buttons let the player take the parts they
 * agree with and leave the rest.
 */
export function ProposedChanges({ changes, appliedSections, onApply }: Props) {
  const sections = groupBySection(changes)
  const pending = sections.filter(([section]) => !appliedSections.includes(section))

  return (
    <div className="space-y-2 border-t pt-2">
      <div className="flex items-center gap-2">
        <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
          Предлагаемые изменения листа
        </p>
        {pending.length > 1 && (
          <Button
            size="sm"
            variant="outline"
            className="ml-auto h-6 text-xs"
            onClick={() => onApply('*', pending.flatMap(([, entries]) => entries))}
          >
            Применить всё
          </Button>
        )}
      </div>

      {sections.map(([section, entries]) => {
        const done = appliedSections.includes(section)
        return (
          <div key={section} className="rounded border bg-background/40 p-2">
            <div className="mb-1 flex items-center gap-2">
              <span className="text-xs font-medium">{section}</span>
              <span className="text-[10px] text-muted-foreground">{entries.length}</span>
              {done ? (
                <span className="ml-auto text-[10px] text-muted-foreground">применено</span>
              ) : (
                <Button
                  size="sm"
                  className="ml-auto h-6 text-xs"
                  onClick={() => onApply(section, entries)}
                >
                  <Check className="size-3" />
                  Применить
                </Button>
              )}
            </div>

            <ul className="space-y-1 text-xs">
              {entries.map((change) => (
                <li key={change.path} className="flex flex-wrap items-baseline gap-1.5">
                  <span className="font-medium">{change.label || change.path}</span>
                  <span className="font-sans text-muted-foreground">
                    {describe(change.before)} → {describe(change.value)}
                  </span>
                  {change.reason && (
                    <span className="text-muted-foreground">· {change.reason}</span>
                  )}
                  {/* Range checks pass any plausible number, so an unchecked
                      sum is worth saying out loud. Text and cards have no
                      arithmetic to vouch for, so they claim nothing. */}
                  {typeof change.value === 'number' &&
                    (change.verified ? (
                      <span
                        className="text-[10px] uppercase tracking-wide text-muted-foreground"
                        title="Ассистент показал расчёт, и он сошёлся с листом"
                      >
                        расчёт сверен
                      </span>
                    ) : (
                      <span
                        className="text-[10px] uppercase tracking-wide text-amber-600 dark:text-amber-500"
                        title="Ассистент не показал, от какого значения считал — проверь число сам"
                      >
                        без выкладки
                      </span>
                    ))}
                </li>
              ))}
            </ul>
          </div>
        )
      })}
    </div>
  )
}
