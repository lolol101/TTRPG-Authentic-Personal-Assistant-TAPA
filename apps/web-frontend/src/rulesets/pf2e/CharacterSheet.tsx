import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { SheetVersions } from '@/components/SheetVersions'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { Character, CharacterUpdate } from '@/lib/api'
import { draftFrom, nextDraft } from '@/rulesets/pf2e/draft'
import { computeMaxHp, EMPTY_COMPONENTS, type AbilityKey, type StatComponents } from '@/rulesets/pf2e/domain'
import { SheetProvider, toNumber, type SheetApi } from '@/rulesets/pf2e/sheetContext'
import { BioTab } from '@/rulesets/pf2e/tabs/BioTab'
import { FeatsGearTab } from '@/rulesets/pf2e/tabs/FeatsGearTab'
import { MainTab } from '@/rulesets/pf2e/tabs/MainTab'
import { SpellsTab } from '@/rulesets/pf2e/tabs/SpellsTab'
import type { Pf2eSheetData } from '@/rulesets/pf2e/types'

interface Props {
  character: Character
  token: string
  onSave: (payload: CharacterUpdate) => Promise<void>
  onDelete: () => Promise<void>
  onBack: () => void
  /** Reloads the character after a saved version is written back over it. */
  onReload: () => Promise<void>
}

const DEFAULT_HP = { ancestry: 0, per_level: 0, item: 0, other: 0, penalty: 0, temporary: 0 }

export function CharacterSheet({ character, token, onSave, onDelete, onBack, onReload }: Props) {
  const [draft, setDraft] = useState<Character>(() => draftFrom(character))
  const [saving, setSaving] = useState(false)
  /** Typed into the sheet and not written back yet — see nextDraft. */
  const [dirty, setDirty] = useState(false)

  // The stored character moves under the sheet whenever a proposal is applied
  // from the chat or a version is restored, and the sheet has to follow it —
  // without throwing away typing that exists nowhere else.
  useEffect(() => {
    setDraft((current) => nextDraft(current, character, dirty))
    // `dirty` is deliberately not a dependency: this runs when the stored
    // character changes, not when the player starts typing.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [character])

  const sheet = draft.sheet_data as Pf2eSheetData

  /** Every edit goes through here, so nothing can change the draft quietly. */
  function editDraft(update: (current: Character) => Character) {
    setDirty(true)
    setDraft(update)
  }

  const api: SheetApi = {
    draft,
    sheet,
    setField: (key, value) => editDraft((current) => ({ ...current, [key]: value })),
    setNumberField: (key, raw) =>
      editDraft((current) => ({ ...current, [key]: toNumber(raw) as Character[typeof key] })),
    patchSheet: (patch) =>
      editDraft((current) => ({
        ...current,
        sheet_data: { ...(current.sheet_data as Pf2eSheetData), ...patch },
      })),
    componentsFor: (key) => (sheet.stats?.[key] as StatComponents) ?? EMPTY_COMPONENTS,
    setComponents: (key, next) =>
      editDraft((current) => {
        const currentSheet = current.sheet_data as Pf2eSheetData
        return {
          ...current,
          sheet_data: { ...currentSheet, stats: { ...currentSheet.stats, [key]: next } },
        }
      }),
    abilityMod: (ability: AbilityKey) => draft[`${ability}_mod` as const],
    setAbility: (ability, next) =>
      editDraft((current) => {
        const currentSheet = current.sheet_data as Pf2eSheetData
        return {
          ...current,
          [`${ability}_mod`]: next.modifier,
          sheet_data: {
            ...currentSheet,
            ability_scores: { ...currentSheet.ability_scores, [ability]: next.score },
          },
        }
      }),
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
      setDirty(false)
    } finally {
      setSaving(false)
    }
  }

  /** Leaving throws the draft away, so it has to be worth throwing away. */
  function handleBack() {
    if (dirty && !window.confirm('В листе есть несохранённые правки. Уйти и потерять их?')) return
    onBack()
  }

  return (
    <SheetProvider value={api}>
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="ghost" onClick={handleBack}>
            ← К списку
          </Button>
          {dirty && (
            <span className="text-xs text-amber-600 dark:text-amber-500">
              есть несохранённые правки
            </span>
          )}
          <div className="ml-auto flex gap-2">
            <SheetVersions token={token} characterId={character.id} onRestored={onReload} />
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
