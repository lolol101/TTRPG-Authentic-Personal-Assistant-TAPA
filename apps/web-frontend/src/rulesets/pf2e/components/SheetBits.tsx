import { Plus, X } from 'lucide-react'
import { CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'
import {
  PROFICIENCY_LABEL,
  PROFICIENCY_RANKS,
  PROFICIENCY_SHORT,
  type ProficiencyRank,
} from '@/rulesets/pf2e/domain'

export function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <CardTitle className="font-heading heading-marked text-2xl font-normal">{children}</CardTitle>
  )
}

export function Field({
  label,
  value,
  onChange,
  type = 'text',
  className,
  inputClassName,
}: {
  label: string
  value: string | number
  onChange: (value: string) => void
  type?: string
  className?: string
  inputClassName?: string
}) {
  return (
    <label className={cn('block space-y-1', className)}>
      <span className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</span>
      <Input
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={cn('h-8', inputClassName)}
      />
    </label>
  )
}

/** The И/Э/М/Л boxes printed beside every statistic. */
export function RankPips({
  rank,
  onChange,
  className,
}: {
  rank: ProficiencyRank
  onChange: (rank: ProficiencyRank) => void
  className?: string
}) {
  return (
    <span className={cn('inline-flex gap-0.5', className)}>
      {PROFICIENCY_RANKS.filter((entry) => entry !== 'untrained').map((entry) => {
        const active = PROFICIENCY_RANKS.indexOf(rank) >= PROFICIENCY_RANKS.indexOf(entry)
        return (
          <button
            key={entry}
            type="button"
            title={PROFICIENCY_LABEL[entry]}
            // Clicking the rank you already hold clears back to untrained,
            // which is how you undo a misclick without cycling all the way round.
            onClick={() => onChange(rank === entry ? 'untrained' : entry)}
            className={cn(
              'size-5 rounded-[3px] border text-[10px] font-semibold leading-none transition-colors',
              active
                ? 'border-secondary bg-secondary text-secondary-foreground'
                : 'border-border hover:bg-muted',
            )}
          >
            {PROFICIENCY_SHORT[entry]}
          </button>
        )
      })}
    </span>
  )
}

export function LabeledRankRow({
  label,
  rank,
  onChange,
}: {
  label: string
  rank: ProficiencyRank
  onChange: (rank: ProficiencyRank) => void
}) {
  return (
    <div className="flex items-center justify-between gap-2 rounded-md border bg-card/60 px-2.5 py-1.5">
      <span className="text-xs">{label}</span>
      <RankPips rank={rank} onChange={onChange} />
    </div>
  )
}

/**
 * A repeating block, as on the printed sheet — except the paper has a fixed
 * number of lines and this grows on demand.
 */
export function RepeatingList<T>({
  items,
  onChange,
  blank,
  addLabel,
  renderRow,
  className,
}: {
  items: T[]
  onChange: (items: T[]) => void
  blank: T
  addLabel: string
  renderRow: (item: T, update: (next: T) => void, index: number) => React.ReactNode
  className?: string
}) {
  return (
    <div className={cn('space-y-2', className)}>
      {items.map((item, index) => (
        <div key={index} className="relative rounded-md border bg-card/60 p-2.5 pr-9">
          {renderRow(
            item,
            (next) => onChange(items.map((entry, i) => (i === index ? next : entry))),
            index,
          )}
          <button
            type="button"
            title="Удалить"
            onClick={() => onChange(items.filter((_, i) => i !== index))}
            className="absolute right-2 top-2 rounded p-1 text-muted-foreground hover:bg-muted hover:text-destructive"
          >
            <X className="size-3.5" />
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={() => onChange([...items, structuredClone(blank)])}
        className="flex items-center gap-1.5 rounded-md border border-dashed px-3 py-1.5 text-xs text-muted-foreground hover:bg-muted"
      >
        <Plus className="size-3.5" />
        {addLabel}
      </button>
    </div>
  )
}

export function FixedSlotList({
  slots,
  entries,
  onChange,
  emptyLabel,
}: {
  slots: string[]
  entries: { slot: string; name: string }[]
  onChange: (entries: { slot: string; name: string }[]) => void
  emptyLabel?: string
}) {
  function valueFor(slot: string): string {
    return entries.find((entry) => entry.slot === slot)?.name ?? ''
  }

  function setValue(slot: string, name: string) {
    const rest = entries.filter((entry) => entry.slot !== slot)
    onChange(name ? [...rest, { slot, name }] : rest)
  }

  return (
    <div className="space-y-1.5">
      {slots.map((slot) => (
        <div key={slot} className="flex items-center gap-2">
          <Input
            value={valueFor(slot)}
            onChange={(event) => setValue(slot, event.target.value)}
            placeholder={emptyLabel}
            className="h-8 flex-1"
          />
          <span className="w-28 shrink-0 text-right text-[10px] uppercase tracking-wide text-muted-foreground">
            {slot}
          </span>
        </div>
      ))}
    </div>
  )
}

export function BigNumber({
  label,
  value,
  onChange,
  readOnly,
  hint,
}: {
  label: string
  value: number
  onChange?: (value: string) => void
  readOnly?: boolean
  hint?: string
}) {
  return (
    <div className="space-y-1">
      <Label className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</Label>
      {readOnly ? (
        <div className="flex h-12 items-center justify-center rounded-md border bg-muted/40 font-sans text-2xl font-semibold tabular-nums">
          {value}
        </div>
      ) : (
        <Input
          type="number"
          value={value}
          onChange={(event) => onChange?.(event.target.value)}
          className="h-12 text-center font-sans text-2xl font-semibold tabular-nums"
        />
      )}
      {hint && <p className="text-[10px] text-muted-foreground">{hint}</p>}
    </div>
  )
}
