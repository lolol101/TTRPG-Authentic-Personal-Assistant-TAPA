import { ChevronDown } from 'lucide-react'
import { useState } from 'react'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import {
  computeStat,
  formatModifier,
  PROFICIENCY_LABEL,
  PROFICIENCY_RANKS,
  PROFICIENCY_SHORT,
  type ProficiencyRank,
  type StatComponents,
} from '@/lib/pf2e'

interface Props {
  label: string
  abilityLabel: string
  abilityMod: number
  level: number
  components: StatComponents
  onChange: (next: StatComponents) => void
  /** 10 for AC and class DC; omitted for skills, saves and Perception. */
  base?: number
  armorPenalty?: number
  hint?: string
}

export function StatRow({
  label,
  abilityLabel,
  abilityMod,
  level,
  components,
  onChange,
  base,
  armorPenalty,
  hint,
}: Props) {
  const [open, setOpen] = useState(false)
  const { total, parts } = computeStat({
    abilityMod,
    abilityLabel,
    level,
    components,
    base,
    armorPenalty,
  })

  function setRank(rank: ProficiencyRank) {
    onChange({ ...components, rank })
  }

  function setNumber(key: 'item' | 'temporary', raw: string) {
    const parsed = Number.parseInt(raw, 10)
    onChange({ ...components, [key]: Number.isNaN(parsed) ? 0 : parsed })
  }

  return (
    <div className="rounded-md border bg-card/60">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-muted/60"
      >
        <span className="flex-1 text-sm">{label}</span>
        {hint && <span className="text-[10px] uppercase text-muted-foreground">{hint}</span>}
        <span
          title={PROFICIENCY_LABEL[components.rank]}
          className={cn(
            'flex h-5 w-5 items-center justify-center rounded-full border text-[10px] font-semibold',
            components.rank === 'untrained'
              ? 'border-dashed text-muted-foreground'
              : 'border-secondary bg-secondary text-secondary-foreground',
          )}
        >
          {PROFICIENCY_SHORT[components.rank]}
        </span>
        <span className="w-10 text-right font-sans text-base font-semibold tabular-nums">
          {formatModifier(total)}
        </span>
        <ChevronDown
          className={cn('size-4 text-muted-foreground transition-transform', open && 'rotate-180')}
        />
      </button>

      {open && (
        <div className="space-y-3 border-t bg-background/40 px-3 py-3">
          <div className="flex flex-wrap gap-1">
            {PROFICIENCY_RANKS.map((rank) => (
              <button
                key={rank}
                type="button"
                onClick={() => setRank(rank)}
                className={cn(
                  'rounded border px-2 py-1 text-xs transition-colors',
                  rank === components.rank
                    ? 'border-secondary bg-secondary text-secondary-foreground'
                    : 'hover:bg-muted',
                )}
              >
                {PROFICIENCY_LABEL[rank]}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-2 gap-2">
            <label className="space-y-1 text-xs text-muted-foreground">
              Бонус предмета
              <Input
                type="number"
                className="h-8"
                value={components.item}
                onChange={(e) => setNumber('item', e.target.value)}
              />
            </label>
            <label className="space-y-1 text-xs text-muted-foreground">
              Временный модификатор
              <Input
                type="number"
                className="h-8"
                value={components.temporary}
                onChange={(e) => setNumber('temporary', e.target.value)}
              />
            </label>
          </div>

          <p className="font-sans text-xs text-muted-foreground">
            {parts.map((part) => `${part.label} ${formatModifier(part.value)}`).join('  ·  ')}
            {'  =  '}
            <span className="font-semibold text-foreground">{formatModifier(total)}</span>
          </p>
        </div>
      )}
    </div>
  )
}
