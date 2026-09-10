import { useState } from 'react'
import { StatRow } from '@/components/StatRow'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { Textarea } from '@/components/ui/textarea'
import type { Character, CharacterUpdate, SheetData } from '@/lib/api'
import { cn } from '@/lib/utils'
import {
  ABILITIES,
  CONDITIONS,
  computeMaxHp,
  EMPTY_COMPONENTS,
  formatModifier,
  SAVES,
  SKILLS,
  type AbilityKey,
  type StatComponents,
} from '@/lib/pf2e'

interface Props {
  character: Character
  onSave: (payload: CharacterUpdate) => Promise<void>
  onDelete: () => Promise<void>
  onBack: () => void
}

const DEFAULT_HP: NonNullable<SheetData['hp']> = {
  ancestry: 0,
  per_level: 0,
  item: 0,
  other: 0,
  penalty: 0,
  temporary: 0,
}

/**
 * Older sheets stored only a flat hp_max. Seeding it into `other` keeps the
 * computed maximum identical while the composition starts out empty.
 */
function initialSheetData(character: Character): SheetData {
  const data = character.sheet_data ?? {}
  if (data.hp) return data
  return { ...data, hp: { ...DEFAULT_HP, other: character.hp_max } }
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <CardTitle className="font-heading heading-marked text-2xl font-normal">{children}</CardTitle>
  )
}

function Field({
  id,
  label,
  value,
  onChange,
  type = 'text',
  className,
}: {
  id: string
  label: string
  value: string | number
  onChange: (value: string) => void
  type?: string
  className?: string
}) {
  return (
    <div className={cn('space-y-1', className)}>
      <Label htmlFor={id} className="text-[11px] uppercase tracking-wide text-muted-foreground">
        {label}
      </Label>
      <Input id={id} type={type} value={value} onChange={(e) => onChange(e.target.value)} />
    </div>
  )
}

export function CharacterSheet({ character, onSave, onDelete, onBack }: Props) {
  const [draft, setDraft] = useState<Character>({
    ...character,
    sheet_data: initialSheetData(character),
  })
  const [saving, setSaving] = useState(false)

  const sheet = draft.sheet_data
  const hp = sheet.hp ?? DEFAULT_HP
  const conditions = sheet.conditions ?? {}

  function set<K extends keyof Character>(key: K, value: Character[K]) {
    setDraft((current) => ({ ...current, [key]: value }))
  }

  function setNumber<K extends keyof Character>(key: K, raw: string) {
    const parsed = Number.parseInt(raw, 10)
    set(key, (Number.isNaN(parsed) ? 0 : parsed) as Character[K])
  }

  function patchSheet(patch: Partial<SheetData>) {
    setDraft((current) => ({ ...current, sheet_data: { ...current.sheet_data, ...patch } }))
  }

  function componentsFor(key: string): StatComponents {
    return sheet.stats?.[key] ?? EMPTY_COMPONENTS
  }

  function setComponents(key: string, next: StatComponents) {
    setDraft((current) => ({
      ...current,
      sheet_data: {
        ...current.sheet_data,
        stats: { ...current.sheet_data.stats, [key]: next },
      },
    }))
  }

  function abilityMod(ability: AbilityKey): number {
    return draft[`${ability}_mod` as const]
  }

  function setHp(key: keyof typeof DEFAULT_HP, raw: string) {
    const parsed = Number.parseInt(raw, 10)
    patchSheet({ hp: { ...hp, [key]: Number.isNaN(parsed) ? 0 : parsed } })
  }

  function toggleCondition(key: string, valued: boolean) {
    const current = conditions[key] ?? 0
    const next = { ...conditions }
    if (valued) {
      const raised = current + 1
      if (raised > 4) delete next[key]
      else next[key] = raised
    } else if (current) {
      delete next[key]
    } else {
      next[key] = 1
    }
    patchSheet({ conditions: next })
  }

  const maxHp = computeMaxHp({
    ancestry: hp.ancestry,
    perLevel: hp.per_level,
    conMod: draft.con_mod,
    level: draft.level,
    item: hp.item,
    other: hp.other,
    penalty: hp.penalty,
  })

  const armorPenalty = sheet.armor?.check_penalty ?? 0
  const dexCap = sheet.armor?.dex_cap ?? null
  const cappedDex = dexCap === null ? draft.dex_mod : Math.min(draft.dex_mod, dexCap)
  const classDcAbility = (sheet.class_dc_ability as AbilityKey) ?? 'str'
  const heroPoints = sheet.hero_points ?? 0

  async function handleSave() {
    setSaving(true)
    try {
      const { id: _id, owner_id: _ownerId, ...rest } = draft
      // The typed columns stay the totals the backend can query; the
      // component breakdown that produced them rides along in sheet_data.
      await onSave({ ...rest, hp_max: maxHp })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="ghost" onClick={onBack}>
          ← К списку
        </Button>
        <div className="ml-auto flex gap-2">
          <Button variant="destructive" onClick={onDelete}>
            Удалить
          </Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? 'Сохраняю…' : 'Сохранить'}
          </Button>
        </div>
      </div>

      <Card>
        <CardContent className="space-y-4 pt-6">
          <div className="grid gap-3 md:grid-cols-[2fr_1fr_1fr]">
            <div className="space-y-1">
              <Label htmlFor="name" className="text-[11px] uppercase tracking-wide text-muted-foreground">
                Имя персонажа
              </Label>
              <Input
                id="name"
                value={draft.name}
                onChange={(e) => set('name', e.target.value)}
                className="font-heading h-12 text-2xl"
              />
            </div>
            <Field
              id="level"
              label="Уровень"
              type="number"
              value={draft.level}
              onChange={(v) => setNumber('level', v)}
            />
            <div className="space-y-1">
              <Label className="text-[11px] uppercase tracking-wide text-muted-foreground">
                Очки героя
              </Label>
              <div className="flex gap-1 pt-1">
                {[1, 2, 3].map((point) => (
                  <button
                    key={point}
                    type="button"
                    onClick={() => patchSheet({ hero_points: heroPoints === point ? 0 : point })}
                    className={cn(
                      'size-8 rounded-full border-2 transition-colors',
                      point <= heroPoints ? 'border-primary bg-primary' : 'border-muted-foreground/40',
                    )}
                    title={`${point} очк.`}
                  />
                ))}
              </div>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Field
              id="ancestry"
              label="Народ"
              value={draft.ancestry}
              onChange={(v) => set('ancestry', v)}
            />
            <Field
              id="heritage"
              label="Наследие"
              value={sheet.heritage ?? ''}
              onChange={(v) => patchSheet({ heritage: v })}
            />
            <Field
              id="background"
              label="Предыстория"
              value={draft.background}
              onChange={(v) => set('background', v)}
            />
            <Field
              id="class_name"
              label="Класс"
              value={draft.class_name}
              onChange={(v) => set('class_name', v)}
            />
            <Field
              id="deity"
              label="Божество"
              value={sheet.deity ?? ''}
              onChange={(v) => patchSheet({ deity: v })}
            />
            <Field
              id="languages"
              label="Языки"
              value={sheet.languages ?? ''}
              onChange={(v) => patchSheet({ languages: v })}
            />
            <Field
              id="senses"
              label="Чувства"
              value={sheet.senses ?? ''}
              onChange={(v) => patchSheet({ senses: v })}
            />
            <Field
              id="player_name"
              label="Игрок"
              value={sheet.player_name ?? ''}
              onChange={(v) => patchSheet({ player_name: v })}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <SectionTitle>Характеристики</SectionTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-3 gap-3 sm:grid-cols-6">
          {ABILITIES.map((ability) => (
            <div
              key={ability.key}
              className="flex flex-col items-center gap-1 rounded-md border bg-card/60 p-3"
            >
              <span className="text-xs font-semibold tracking-wide" title={ability.full}>
                {ability.label}
              </span>
              <Input
                type="number"
                className="h-11 w-16 text-center font-sans text-xl font-semibold tabular-nums"
                value={draft[`${ability.key}_mod` as const]}
                onChange={(e) => setNumber(`${ability.key}_mod` as const, e.target.value)}
              />
            </div>
          ))}
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <SectionTitle>Защита</SectionTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <StatRow
              label="Класс брони"
              abilityLabel="ЛОВ"
              abilityMod={cappedDex}
              level={draft.level}
              base={10}
              components={componentsFor('armor_class')}
              onChange={(next) => setComponents('armor_class', next)}
              hint={dexCap === null ? undefined : `лимит ЛОВ ${formatModifier(dexCap)}`}
            />

            <div className="grid grid-cols-2 gap-2">
              <Field
                id="dex_cap"
                label="Лимит ЛОВ от брони"
                type="number"
                value={dexCap ?? ''}
                onChange={(v) =>
                  patchSheet({
                    armor: {
                      check_penalty: armorPenalty,
                      dex_cap: v === '' ? null : Number.parseInt(v, 10) || 0,
                    },
                  })
                }
              />
              <Field
                id="check_penalty"
                label="Штраф проверок брони"
                type="number"
                value={armorPenalty}
                onChange={(v) =>
                  patchSheet({
                    armor: { dex_cap: dexCap, check_penalty: Number.parseInt(v, 10) || 0 },
                  })
                }
              />
            </div>

            <Separator />

            {SAVES.map((save) => (
              <StatRow
                key={save.key}
                label={save.label}
                abilityLabel={ABILITIES.find((a) => a.key === save.ability)!.label}
                abilityMod={abilityMod(save.ability)}
                level={draft.level}
                components={componentsFor(save.key)}
                onChange={(next) => setComponents(save.key, next)}
              />
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <SectionTitle>Здоровье</SectionTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-end gap-3">
              <div className="flex-1 space-y-1">
                <Label
                  htmlFor="hp_current"
                  className="text-[11px] uppercase tracking-wide text-muted-foreground"
                >
                  Текущие ХП
                </Label>
                <Input
                  id="hp_current"
                  type="number"
                  className="h-14 text-center font-sans text-3xl font-semibold tabular-nums"
                  value={draft.hp_current}
                  onChange={(e) => setNumber('hp_current', e.target.value)}
                />
              </div>
              <div className="pb-4 text-2xl text-muted-foreground">/</div>
              <div className="flex-1 space-y-1">
                <Label className="text-[11px] uppercase tracking-wide text-muted-foreground">
                  Максимум (считается)
                </Label>
                <div className="flex h-14 items-center justify-center rounded-md border bg-muted/40 font-sans text-3xl font-semibold tabular-nums">
                  {maxHp}
                </div>
              </div>
              <div className="w-24 space-y-1">
                <Label
                  htmlFor="temp_hp"
                  className="text-[11px] uppercase tracking-wide text-muted-foreground"
                >
                  Временные
                </Label>
                <Input
                  id="temp_hp"
                  type="number"
                  className="h-14 text-center font-sans text-2xl tabular-nums"
                  value={hp.temporary}
                  onChange={(e) => setHp('temporary', e.target.value)}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              <Field
                id="hp_ancestry"
                label="От народа"
                type="number"
                value={hp.ancestry}
                onChange={(v) => setHp('ancestry', v)}
              />
              <Field
                id="hp_per_level"
                label="От класса за уровень"
                type="number"
                value={hp.per_level}
                onChange={(v) => setHp('per_level', v)}
              />
              <Field
                id="hp_item"
                label="От предметов"
                type="number"
                value={hp.item}
                onChange={(v) => setHp('item', v)}
              />
              <Field
                id="hp_other"
                label="Прочее"
                type="number"
                value={hp.other}
                onChange={(v) => setHp('other', v)}
              />
              <Field
                id="hp_penalty"
                label="Штраф"
                type="number"
                value={hp.penalty}
                onChange={(v) => setHp('penalty', v)}
              />
              <Field
                id="speed"
                label="Скорость"
                type="number"
                value={draft.speed}
                onChange={(v) => setNumber('speed', v)}
              />
            </div>

            <p className="font-sans text-xs text-muted-foreground">
              {hp.ancestry} + ({hp.per_level} от класса {formatModifier(draft.con_mod)} ТЕЛ) ×{' '}
              {draft.level} ур. = {maxHp}
            </p>

            <Separator />

            <StatRow
              label="Восприятие"
              abilityLabel="МДР"
              abilityMod={draft.wis_mod}
              level={draft.level}
              components={componentsFor('perception')}
              onChange={(next) => setComponents('perception', next)}
            />
            <StatRow
              label="КС класса"
              abilityLabel={ABILITIES.find((a) => a.key === classDcAbility)!.label}
              abilityMod={abilityMod(classDcAbility)}
              level={draft.level}
              base={10}
              components={componentsFor('class_dc')}
              onChange={(next) => setComponents('class_dc', next)}
            />
            <div className="flex flex-wrap items-center gap-1">
              <span className="mr-1 text-xs text-muted-foreground">Ключевая характеристика:</span>
              {ABILITIES.map((ability) => (
                <button
                  key={ability.key}
                  type="button"
                  onClick={() => patchSheet({ class_dc_ability: ability.key })}
                  className={cn(
                    'rounded border px-2 py-0.5 text-xs',
                    ability.key === classDcAbility
                      ? 'border-secondary bg-secondary text-secondary-foreground'
                      : 'hover:bg-muted',
                  )}
                >
                  {ability.label}
                </button>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <SectionTitle>Навыки</SectionTitle>
        </CardHeader>
        <CardContent className="grid gap-2 lg:grid-cols-2">
          {SKILLS.map((skill) => (
            <StatRow
              key={skill.key}
              label={skill.label}
              abilityLabel={ABILITIES.find((a) => a.key === skill.ability)!.label}
              abilityMod={abilityMod(skill.ability)}
              level={draft.level}
              components={componentsFor(skill.key)}
              onChange={(next) => setComponents(skill.key, next)}
              armorPenalty={skill.armorPenalty ? armorPenalty : 0}
              hint={ABILITIES.find((a) => a.key === skill.ability)!.label}
            />
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <SectionTitle>Состояния</SectionTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {CONDITIONS.map((condition) => {
            const value = conditions[condition.key] ?? 0
            return (
              <button
                key={condition.key}
                type="button"
                onClick={() => toggleCondition(condition.key, condition.valued)}
                title={
                  condition.valued
                    ? 'Нажимай, чтобы поднять значение (сбросится после 4)'
                    : undefined
                }
                className={cn(
                  'rounded-full border px-3 py-1 text-xs transition-colors',
                  value
                    ? 'border-primary bg-primary text-primary-foreground'
                    : 'border-dashed text-muted-foreground hover:bg-muted',
                )}
              >
                {condition.label}
                {condition.valued && value > 0 && ` ${value}`}
              </button>
            )
          })}
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <SectionTitle>Сопротивления и иммунитеты</SectionTitle>
          </CardHeader>
          <CardContent>
            <Textarea
              rows={4}
              value={sheet.resistances ?? ''}
              onChange={(e) => patchSheet({ resistances: e.target.value })}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <SectionTitle>Заметки</SectionTitle>
          </CardHeader>
          <CardContent>
            <Textarea
              rows={4}
              value={sheet.notes ?? ''}
              onChange={(e) => patchSheet({ notes: e.target.value })}
            />
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
