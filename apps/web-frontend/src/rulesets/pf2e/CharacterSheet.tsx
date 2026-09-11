import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { Character, CharacterUpdate } from '@/lib/api'
import { computeMaxHp, EMPTY_COMPONENTS, type AbilityKey, type StatComponents } from '@/rulesets/pf2e/domain'
import { SheetProvider, toNumber, type SheetApi } from '@/rulesets/pf2e/sheetContext'
import { BioTab } from '@/rulesets/pf2e/tabs/BioTab'
import { FeatsGearTab } from '@/rulesets/pf2e/tabs/FeatsGearTab'
import { MainTab } from '@/rulesets/pf2e/tabs/MainTab'
import { SpellsTab } from '@/rulesets/pf2e/tabs/SpellsTab'
import type { Pf2eSheetData } from '@/rulesets/pf2e/types'

interface Props {
  character: Character
  onSave: (payload: CharacterUpdate) => Promise<void>
  onDelete: () => Promise<void>
  onBack: () => void
}

const DEFAULT_HP = { ancestry: 0, per_level: 0, item: 0, other: 0, penalty: 0, temporary: 0 }

/**
 * Older sheets stored only a flat hp_max. Seeding it into `other` keeps the
 * computed maximum identical while the composition starts out empty.
 */
function initialSheetData(character: Character): Pf2eSheetData {
  const data = (character.sheet_data ?? {}) as Pf2eSheetData
  if (data.hp) return data
  return { ...data, hp: { ...DEFAULT_HP, other: character.hp_max } }
}

export function CharacterSheet({ character, onSave, onDelete, onBack }: Props) {
  const [draft, setDraft] = useState<Character>({
    ...character,
    sheet_data: initialSheetData(character),
  })
  const [saving, setSaving] = useState(false)

  const sheet = draft.sheet_data as Pf2eSheetData

  const api: SheetApi = {
    draft,
    sheet,
    setField: (key, value) => setDraft((current) => ({ ...current, [key]: value })),
    setNumberField: (key, raw) =>
      setDraft((current) => ({ ...current, [key]: toNumber(raw) as Character[typeof key] })),
    patchSheet: (patch) =>
      setDraft((current) => ({
        ...current,
        sheet_data: { ...(current.sheet_data as Pf2eSheetData), ...patch },
      })),
    componentsFor: (key) => (sheet.stats?.[key] as StatComponents) ?? EMPTY_COMPONENTS,
    setComponents: (key, next) =>
      setDraft((current) => {
        const currentSheet = current.sheet_data as Pf2eSheetData
        return {
          ...current,
          sheet_data: { ...currentSheet, stats: { ...currentSheet.stats, [key]: next } },
        }
      }),
    abilityMod: (ability: AbilityKey) => draft[`${ability}_mod` as const],
  }

  async function handleSave() {
    setSaving(true)
    try {
      const hp = sheet.hp ?? DEFAULT_HP
      const { id: _id, owner_id: _ownerId, ...rest } = draft
      // Typed columns carry the totals the backend queries; the components
      // that produced them ride along inside sheet_data.
      await onSave({
        ...rest,
        hp_max: computeMaxHp({
          ancestry: hp.ancestry,
          perLevel: hp.per_level,
          conMod: draft.con_mod,
          level: draft.level,
          item: hp.item,
          other: hp.other,
          penalty: hp.penalty,
        }),
      })
    } finally {
      setSaving(false)
    }
  }

  return (
    <SheetProvider value={api}>
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

        <Tabs defaultValue="main">
          <TabsList>
            <TabsTrigger value="main">Основное</TabsTrigger>
            <TabsTrigger value="feats">Черты и снаряжение</TabsTrigger>
            <TabsTrigger value="bio">Личность</TabsTrigger>
            <TabsTrigger value="spells">Заклинания</TabsTrigger>
          </TabsList>

          <TabsContent value="main" className="mt-4">
            <MainTab />
          </TabsContent>
          <TabsContent value="feats" className="mt-4">
            <FeatsGearTab />
          </TabsContent>
          <TabsContent value="bio" className="mt-4">
            <BioTab />
          </TabsContent>
          <TabsContent value="spells" className="mt-4">
            <SpellsTab />
          </TabsContent>
        </Tabs>
      </div>
    </SheetProvider>
  )
}
