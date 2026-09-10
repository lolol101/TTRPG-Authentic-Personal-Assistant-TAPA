import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { cn } from '@/lib/utils'
import { StatRow } from '@/rulesets/pf2e/components/StatRow'
import { Field, RepeatingList, SectionTitle } from '@/rulesets/pf2e/components/SheetBits'
import { ABILITIES, abilityLabel, SPELL_TRADITIONS, type AbilityKey } from '@/rulesets/pf2e/domain'
import { toNumber, useSheet } from '@/rulesets/pf2e/sheetContext'
import { EMPTY_SPELL, type SpellEntry } from '@/rulesets/pf2e/types'

const EMPTY_COMPONENTS = { rank: 'untrained' as const, item: 0, temporary: 0 }
const SPELL_LEVELS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

function SpellList({
  title,
  items,
  onChange,
  showPrepared,
}: {
  title: string
  items: SpellEntry[]
  onChange: (items: SpellEntry[]) => void
  showPrepared?: boolean
}) {
  return (
    <Card>
      <CardHeader>
        <SectionTitle>{title}</SectionTitle>
      </CardHeader>
      <CardContent>
        <RepeatingList
          items={items}
          onChange={onChange}
          blank={EMPTY_SPELL}
          addLabel="Добавить заклинание"
          renderRow={(spell, update) => (
            <div className="flex flex-wrap items-end gap-2">
              <Field
                label="Название"
                value={spell.name}
                onChange={(name) => update({ ...spell, name })}
                className="min-w-40 flex-1"
              />
              <Field
                label="Круг"
                value={spell.level}
                onChange={(level) => update({ ...spell, level })}
                className="w-16"
              />
              <Field
                label="Действия"
                value={spell.actions}
                onChange={(actions) => update({ ...spell, actions })}
                className="w-20"
              />
              {showPrepared && (
                <label className="flex h-8 items-center gap-1.5 text-[10px] uppercase text-muted-foreground">
                  <input
                    type="checkbox"
                    checked={spell.prepared}
                    onChange={(event) => update({ ...spell, prepared: event.target.checked })}
                  />
                  Подг.
                </label>
              )}
            </div>
          )}
        />
      </CardContent>
    </Card>
  )
}

export function SpellsTab() {
  const { draft, sheet, patchSheet, abilityMod } = useSheet()

  const casting = sheet.spellcasting ?? {}
  const keyAbility: AbilityKey = casting.key_ability ?? 'cha'
  const slots = casting.slots ?? []
  const focusPoints = casting.focus_points ?? { current: 0, max: 0 }

  function patchCasting(patch: Partial<typeof casting>) {
    patchSheet({ spellcasting: { ...casting, ...patch } })
  }

  function slotFor(level: number) {
    return slots.find((slot) => slot.level === level) ?? { level, max: 0, remaining: 0 }
  }

  function setSlot(level: number, key: 'max' | 'remaining', raw: string) {
    const current = slotFor(level)
    const next = { ...current, [key]: toNumber(raw) }
    patchCasting({ slots: [...slots.filter((slot) => slot.level !== level), next] })
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <SectionTitle>Заклинательство</SectionTitle>
          </CardHeader>
          <CardContent className="space-y-3">
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
              <span className="mr-1 text-[10px] uppercase text-muted-foreground">
                Ключевая хар.:
              </span>
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
              {SPELL_TRADITIONS.map((tradition) => (
                <button
                  key={tradition.key}
                  type="button"
                  onClick={() => patchCasting({ tradition: tradition.key })}
                  className={cn(
                    'rounded border px-2.5 py-1 text-xs',
                    casting.tradition === tradition.key
                      ? 'border-secondary bg-secondary text-secondary-foreground'
                      : 'hover:bg-muted',
                  )}
                >
                  {tradition.label}
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
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <SectionTitle>Ячейки заклинаний в день</SectionTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
              {SPELL_LEVELS.map((level) => {
                const slot = slotFor(level)
                return (
                  <div key={level} className="rounded-md border bg-card/60 p-1.5">
                    <p className="text-center text-[10px] font-semibold text-muted-foreground">
                      {level}
                    </p>
                    <Field
                      label="Всего"
                      type="number"
                      value={slot.max}
                      onChange={(value) => setSlot(level, 'max', value)}
                      inputClassName="h-7 text-center font-sans"
                    />
                    <Field
                      label="Остаток"
                      type="number"
                      value={slot.remaining}
                      onChange={(value) => setSlot(level, 'remaining', value)}
                      inputClassName="h-7 text-center font-sans"
                    />
                  </div>
                )
              })}
            </div>

            <Separator />

            <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
              Фокальные пункты
            </p>
            <div className="grid grid-cols-2 gap-2">
              <Field
                label="Текущие"
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
          </CardContent>
        </Card>
      </div>

      <SpellList
        title="Заклинания"
        items={sheet.spells ?? []}
        onChange={(spells) => patchSheet({ spells })}
        showPrepared
      />
      <div className="grid gap-4 lg:grid-cols-2">
        <SpellList
          title="Фокусы"
          items={sheet.focus_spells ?? []}
          onChange={(focus_spells) => patchSheet({ focus_spells })}
        />
        <SpellList
          title="Врождённые заклинания"
          items={sheet.innate_spells ?? []}
          onChange={(innate_spells) => patchSheet({ innate_spells })}
        />
      </div>
    </div>
  )
}
