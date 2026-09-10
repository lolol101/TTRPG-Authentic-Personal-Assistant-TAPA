import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { Textarea } from '@/components/ui/textarea'
import type { Character, CharacterUpdate } from '@/lib/api'
import {
  ABILITIES,
  formatModifier,
  PROFICIENCY_LABEL,
  PROFICIENCY_RANKS,
  PROFICIENCY_SHORT,
  proficiencyBonus,
  SAVES,
  SKILLS,
  type AbilityKey,
  type ProficiencyRank,
} from '@/lib/pf2e'

interface Props {
  character: Character
  onSave: (payload: CharacterUpdate) => Promise<void>
  onDelete: () => Promise<void>
  onBack: () => void
}

function abilityMod(draft: Character, ability: AbilityKey): number {
  return draft[`${ability}_mod` as const]
}

function rankOf(draft: Character, key: string): ProficiencyRank {
  return draft.sheet_data.proficiencies?.[key] ?? 'untrained'
}

/** Cycles untrained → trained → … → legendary → untrained, like clicking the Roll20 rank pips. */
function nextRank(rank: ProficiencyRank): ProficiencyRank {
  const index = PROFICIENCY_RANKS.indexOf(rank)
  return PROFICIENCY_RANKS[(index + 1) % PROFICIENCY_RANKS.length]
}

function StatBox({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border bg-card px-3 py-2">
      <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      <span className="text-2xl font-semibold tabular-nums">{value}</span>
      {hint && <span className="text-[10px] text-muted-foreground">{hint}</span>}
    </div>
  )
}

export function CharacterSheet({ character, onSave, onDelete, onBack }: Props) {
  const [draft, setDraft] = useState<Character>(character)
  const [saving, setSaving] = useState(false)

  function set<K extends keyof Character>(key: K, value: Character[K]) {
    setDraft((current) => ({ ...current, [key]: value }))
  }

  function setNumber<K extends keyof Character>(key: K, raw: string) {
    const parsed = Number.parseInt(raw, 10)
    set(key, (Number.isNaN(parsed) ? 0 : parsed) as Character[K])
  }

  function cycleProficiency(key: string) {
    setDraft((current) => ({
      ...current,
      sheet_data: {
        ...current.sheet_data,
        proficiencies: {
          ...current.sheet_data.proficiencies,
          [key]: nextRank(rankOf(current, key)),
        },
      },
    }))
  }

  async function handleSave() {
    setSaving(true)
    try {
      const { id: _id, owner_id: _ownerId, ...payload } = draft
      await onSave(payload)
    } finally {
      setSaving(false)
    }
  }

  const perceptionRank = rankOf(draft, 'perception')
  const perception = draft.wis_mod + proficiencyBonus(perceptionRank, draft.level)

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
        <CardContent className="grid gap-4 pt-6 md:grid-cols-[2fr_1fr_1fr_1fr_1fr]">
          <div className="space-y-1.5">
            <Label htmlFor="name">Имя персонажа</Label>
            <Input id="name" value={draft.name} onChange={(e) => set('name', e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="level">Уровень</Label>
            <Input
              id="level"
              type="number"
              value={draft.level}
              onChange={(e) => setNumber('level', e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="ancestry">Народ</Label>
            <Input
              id="ancestry"
              value={draft.ancestry}
              onChange={(e) => set('ancestry', e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="background">Предыстория</Label>
            <Input
              id="background"
              value={draft.background}
              onChange={(e) => set('background', e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="class_name">Класс</Label>
            <Input
              id="class_name"
              value={draft.class_name}
              onChange={(e) => set('class_name', e.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm uppercase tracking-wide text-muted-foreground">
            Характеристики
          </CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-3 gap-3 sm:grid-cols-6">
          {ABILITIES.map((ability) => (
            <div
              key={ability.key}
              className="flex flex-col items-center gap-1 rounded-lg border bg-card p-3"
            >
              <span className="text-xs font-semibold" title={ability.full}>
                {ability.label}
              </span>
              <Input
                type="number"
                className="h-10 w-16 text-center text-lg font-semibold tabular-nums"
                value={draft[`${ability.key}_mod` as const]}
                onChange={(e) => setNumber(`${ability.key}_mod` as const, e.target.value)}
              />
            </div>
          ))}
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm uppercase tracking-wide text-muted-foreground">
              Защита
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="ac">КБ</Label>
                <Input
                  id="ac"
                  type="number"
                  value={draft.ac}
                  onChange={(e) => setNumber('ac', e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="speed">Скорость</Label>
                <Input
                  id="speed"
                  type="number"
                  value={draft.speed}
                  onChange={(e) => setNumber('speed', e.target.value)}
                />
              </div>
            </div>

            <Separator />

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="hp_current">ХП сейчас</Label>
                <Input
                  id="hp_current"
                  type="number"
                  value={draft.hp_current}
                  onChange={(e) => setNumber('hp_current', e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="hp_max">ХП максимум</Label>
                <Input
                  id="hp_max"
                  type="number"
                  value={draft.hp_max}
                  onChange={(e) => setNumber('hp_max', e.target.value)}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm uppercase tracking-wide text-muted-foreground">
              Спасброски
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {SAVES.map((save) => {
              const rank = rankOf(draft, save.key)
              const total = abilityMod(draft, save.ability) + proficiencyBonus(rank, draft.level)
              return (
                <button
                  key={save.key}
                  type="button"
                  onClick={() => cycleProficiency(save.key)}
                  title={`${PROFICIENCY_LABEL[rank]} — нажми, чтобы сменить`}
                  className="flex w-full items-center justify-between rounded-md border px-3 py-2 text-left hover:bg-muted"
                >
                  <span className="text-sm">{save.label}</span>
                  <span className="flex items-center gap-2">
                    <Badge variant="secondary">{PROFICIENCY_SHORT[rank]}</Badge>
                    <span className="w-8 text-right font-semibold tabular-nums">
                      {formatModifier(total)}
                    </span>
                  </span>
                </button>
              )
            })}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm uppercase tracking-wide text-muted-foreground">
              Восприятие и бой
            </CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => cycleProficiency('perception')}
              title={`${PROFICIENCY_LABEL[perceptionRank]} — нажми, чтобы сменить`}
              className="col-span-2 rounded-lg border p-0 text-left hover:bg-muted"
            >
              <StatBox
                label="Восприятие"
                value={formatModifier(perception)}
                hint={PROFICIENCY_LABEL[perceptionRank]}
              />
            </button>
            <StatBox label="КБ" value={String(draft.ac)} />
            <StatBox
              label="ХП"
              value={`${draft.hp_current}/${draft.hp_max}`}
              hint={`Скорость ${draft.speed} фт.`}
            />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm uppercase tracking-wide text-muted-foreground">
            Навыки
          </CardTitle>
        </CardHeader>
        <CardContent className="grid gap-2 sm:grid-cols-2">
          {SKILLS.map((skill) => {
            const rank = rankOf(draft, skill.key)
            const total = abilityMod(draft, skill.ability) + proficiencyBonus(rank, draft.level)
            return (
              <button
                key={skill.key}
                type="button"
                onClick={() => cycleProficiency(skill.key)}
                title={`${PROFICIENCY_LABEL[rank]} — нажми, чтобы сменить`}
                className="flex items-center justify-between rounded-md border px-3 py-2 text-left hover:bg-muted"
              >
                <span className="flex items-center gap-2 text-sm">
                  {skill.label}
                  <span className="text-[10px] uppercase text-muted-foreground">
                    {skill.ability}
                  </span>
                </span>
                <span className="flex items-center gap-2">
                  <Badge variant="secondary">{PROFICIENCY_SHORT[rank]}</Badge>
                  <span className="w-8 text-right font-semibold tabular-nums">
                    {formatModifier(total)}
                  </span>
                </span>
              </button>
            )
          })}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm uppercase tracking-wide text-muted-foreground">
            Заметки
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Textarea
            rows={4}
            value={draft.sheet_data.notes ?? ''}
            onChange={(e) =>
              setDraft((current) => ({
                ...current,
                sheet_data: { ...current.sheet_data, notes: e.target.value },
              }))
            }
          />
        </CardContent>
      </Card>
    </div>
  )
}
