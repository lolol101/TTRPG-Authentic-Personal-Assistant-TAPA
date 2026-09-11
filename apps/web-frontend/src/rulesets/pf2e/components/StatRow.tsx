import { ChevronDown } from 'lucide-react'
import { useState } from 'react'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { RankPips } from '@/rulesets/pf2e/components/SheetBits'
import {
  computeStat,
  formatModifier,
  PROFICIENCY_LABEL,
  type StatComponents,
} from '@/rulesets/pf2e/domain'

interface Props {
  label: string
  abilityLabel: string
  abilityMod: number
  level: number
  components: StatComponents
  onChange: (next: StatComponents) => void
  /** 10 for AC, class DC and spell DC; omitted for skills, saves, Perception. */
  base?: number
  armorPenalty?: number
  hint?: string
  className?: string
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
  className,
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

  function setNumber(key: 'item' | 'temporary', raw: string) {
    const parsed = Number.parseInt(raw, 10)
    onChange({ ...components, [key]: Number.isNaN(parsed) ? 0 : parsed })
  }

  return (
    <div className={cn('rounded-md border bg-card/60', className)}>
      <div className="flex items-center gap-2 px-2.5 py-1.5">
        <span className="flex-1 text-sm">{label}</span>
        {hint && <span className="text-[10px] uppercase text-muted-foreground">{hint}</span>}
        <RankPips rank={components.rank} onChange={(rank) => onChange({ ...components, rank })} />
        <span
          className="w-10 text-right font-sans text-base font-semibold tabular-nums"
          title={PROFICIENCY_LABEL[components.rank]}
        >
          {formatModifier(total)}
        </span>
        <button
          type="button"
          onClick={() => setOpen(!open)}
          title="Показать разбор"
          className="rounded p-0.5 text-muted-foreground hover:bg-muted"
        >
          <ChevronDown className={cn('size-4 transition-transform', open && 'rotate-180')} />
        </button>
      </div>

      {open && (
        <div className="space-y-2 border-t bg-background/40 px-2.5 py-2">
          <div className="grid grid-cols-2 gap-2">
            <label className="space-y-1 text-[10px] uppercase tracking-wide text-muted-foreground">
              Предмет
              <Input
                type="number"
                className="h-8"
                value={components.item}
                onChange={(event) => setNumber('item', event.target.value)}
              />
            </label>
            <label className="space-y-1 text-[10px] uppercase tracking-wide text-muted-foreground">
              Временно
              <Input
                type="number"
                className="h-8"
                value={components.temporary}
                onChange={(event) => setNumber('temporary', event.target.value)}
              />
            </label>
          </div>

          <p className="font-sans text-[11px] text-muted-foreground">
            {parts.map((part) => `${part.label} ${formatModifier(part.value)}`).join('  ·  ')}
            {'  =  '}
            <span className="font-semibold text-foreground">{formatModifier(total)}</span>
          </p>
        </div>
      )}
    </div>
  )
}
