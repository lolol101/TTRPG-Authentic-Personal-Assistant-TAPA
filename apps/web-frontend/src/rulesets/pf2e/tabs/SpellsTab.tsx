import { Section } from '@/components/Section'
import { Separator } from '@/components/ui/separator'
import { cn } from '@/lib/utils'
import { SPELL_SCHEMA } from '@/rulesets/pf2e/cards'
import { CardList } from '@/rulesets/pf2e/components/CardList'
import { Field } from '@/rulesets/pf2e/components/SheetBits'
import { StatRow } from '@/rulesets/pf2e/components/StatRow'
import { ABILITIES, abilityLabel, SPELL_TRADITIONS, type AbilityKey } from '@/rulesets/pf2e/domain'
import { toNumber, useSheet } from '@/rulesets/pf2e/sheetContext'

const EMPTY_COMPONENTS = { rank: 'untrained' as const, item: 0, temporary: 0 }
const SPELL_RANKS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

const SPELL_GROUPS = [
  { key: 'spells' as const, title: 'Заклинания', hint: 'Всё, что персонаж знает или готовит.' },
  { key: 'focus_spells' as const, title: 'Фокусы', hint: 'Тратят фокальные пункты.' },
  {
    key: 'innate_spells' as const,
    title: 'Врождённые заклинания',
    hint: 'От народа или предмета.',
  },
]

export function SpellsTab() {
  const { draft, sheet, patchSheet, abilityMod } = useSheet()

  const casting = sheet.spellcasting ?? {}
  const keyAbility: AbilityKey = casting.key_ability ?? 'cha'
  const slots = casting.slots ?? []
  const focusPoints = casting.focus_points ?? { current: 0, max: 0 }

  function patchCasting(patch: Partial<typeof casting>) {
    patchSheet({ spellcasting: { ...casting, ...patch } })
  }

  function slotFor(rank: number) {
    return slots.find((slot) => slot.level === rank) ?? { level: rank, max: 0, remaining: 0 }
  }

  function setSlot(rank: number, key: 'max' | 'remaining', raw: string) {
    const next = { ...slotFor(rank), [key]: toNumber(raw) }
    patchCasting({ slots: [...slots.filter((slot) => slot.level !== rank), next] })
  }

  const tradition = SPELL_TRADITIONS.find((entry) => entry.key === casting.tradition)

  return (
    <div className="grid gap-3 lg:grid-cols-2">
      <Section
        id="pf2e.spellcasting"
        title="Заклинательство"
        defaultOpen
        summary={tradition?.label ?? 'не задано'}
      >
        <div className="space-y-3">
          <StatRow
            label="Проверка атаки заклинанием"
            abilityLabel={abilityLabel(keyAbility)}
            abilityMod={abilityMod(keyAbility)}
            level={draft.level}
            components={casting.attack ?? EMPTY_COMPONENTS}
            onChange={(attack) => patchCasting({ attack })}
          />
          <StatRow
            label="СЛ заклинаний"
            abilityLabel={abilityLabel(keyAbility)}
            abilityMod={abilityMod(keyAbility)}
            level={draft.level}
            base={10}
            components={casting.dc ?? EMPTY_COMPONENTS}
            onChange={(dc) => patchCasting({ dc })}
          />

          <div className="flex flex-wrap items-center gap-1">
            <span className="mr-1 text-[10px] uppercase text-muted-foreground">Ключевая хар.:</span>
            {ABILITIES.map((ability) => (
              <button
                key={ability.key}
                type="button"
                onClick={() => patchCasting({ key_ability: ability.key })}
                className={cn(
                  'rounded border px-2 py-0.5 text-xs',
                  ability.key === keyAbility
                    ? 'border-secondary bg-secondary text-secondary-foreground'
                    : 'hover:bg-muted',
                )}
              >
                {ability.label}
              </button>
            ))}
          </div>

          <Separator />

          <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
            Магическая традиция
          </p>
          <div className="flex flex-wrap gap-1.5">
            {SPELL_TRADITIONS.map((entry) => (
              <button
                key={entry.key}
                type="button"
                onClick={() => patchCasting({ tradition: entry.key })}
                className={cn(
                  'rounded border px-2.5 py-1 text-xs',
                  casting.tradition === entry.key
                    ? 'border-secondary bg-secondary text-secondary-foreground'
                    : 'hover:bg-muted',
                )}
              >
                {entry.label}
              </button>
            ))}
          </div>

          <div className="flex gap-1.5">
            {[
              { value: true, label: 'Подготавливающий' },
              { value: false, label: 'Спонтанный' },
            ].map((mode) => (
              <button
                key={String(mode.value)}
                type="button"
                onClick={() => patchCasting({ prepared: mode.value })}
                className={cn(
                  'rounded border px-2.5 py-1 text-xs',
                  casting.prepared === mode.value
                    ? 'border-secondary bg-secondary text-secondary-foreground'
                    : 'hover:bg-muted',
                )}
              >
                {mode.label}
              </button>
            ))}
          </div>
        </div>
      </Section>

      <Section
        id="pf2e.slots"
        title="Ячейки и фокус"
        defaultOpen
        summary={`фокус ${focusPoints.current}/${focusPoints.max}`}
      >
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
            {SPELL_RANKS.map((rank) => {
              const slot = slotFor(rank)
              return (
                <div key={rank} className="rounded-md border bg-card/60 p-1.5">
                  <p className="text-center text-[10px] font-semibold text-muted-foreground">
                    {rank}
                  </p>
                  <Field
                    label="Всего"
                    type="number"
                    value={slot.max}
                    onChange={(value) => setSlot(rank, 'max', value)}
                    inputClassName="h-7 text-center font-sans"
                  />
                  <Field
                    label="Остаток"
                    type="number"
                    value={slot.remaining}
                    onChange={(value) => setSlot(rank, 'remaining', value)}
                    inputClassName="h-7 text-center font-sans"
                  />
                </div>
              )
            })}
          </div>

          <Separator />

          <div className="grid grid-cols-2 gap-2">
            <Field
              label="Фокальные пункты"
              type="number"
              value={focusPoints.current}
              onChange={(value) =>
                patchCasting({ focus_points: { ...focusPoints, current: toNumber(value) } })
              }
            />
            <Field
              label="Максимум"
              type="number"
              value={focusPoints.max}
              onChange={(value) =>
                patchCasting({ focus_points: { ...focusPoints, max: toNumber(value) } })
              }
            />
          </div>
        </div>
      </Section>

      {SPELL_GROUPS.map((group) => {
        const cards = sheet[group.key] ?? []
        return (
          <Section
            key={group.key}
            id={`pf2e.${group.key}`}
            title={group.title}
            className={group.key === 'spells' ? 'lg:col-span-2' : undefined}
            summary={cards.length ? `${cards.length}` : 'пусто'}
          >
            <CardList
              schema={SPELL_SCHEMA}
              cards={cards}
              onChange={(next) => patchSheet({ [group.key]: next })}
              emptyHint={group.hint}
            />
          </Section>
        )
      })}
    </div>
  )
}
