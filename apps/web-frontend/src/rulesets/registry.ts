import type { ComponentType } from 'react'
import type { Character, CharacterUpdate } from '@/lib/api'
import { CharacterSheet as Pf2eCharacterSheet } from '@/rulesets/pf2e/CharacterSheet'

export interface SheetProps {
  character: Character
  onSave: (payload: CharacterUpdate) => Promise<void>
  onDelete: () => Promise<void>
  onBack: () => void
}

export interface RulesetDef {
  id: string
  label: string
  /** One line shown next to the choice when creating a character. */
  description: string
  Sheet: ComponentType<SheetProps>
}

/**
 * Every game system has its own character sheet. Adding one means adding a
 * directory under src/rulesets/ and an entry here — nothing generic changes.
 */
export const RULESETS: RulesetDef[] = [
  {
    id: 'pf2e',
    label: 'Pathfinder 2e',
    description: 'Официальный бланк Paizo: характеристики, испытания, черты, снаряжение, магия.',
    Sheet: Pf2eCharacterSheet,
  },
]

export const DEFAULT_RULESET = 'pf2e'

/**
 * Systems whose rules are indexed and can be asked about.
 *
 * Separate from RULESETS on purpose: having a searchable rulebook and having
 * a character sheet are different things. D&D 5e is here without a sheet.
 */
export const QUESTION_RULESETS: { id: string; label: string }[] = [
  { id: 'pf2e', label: 'Pathfinder 2e' },
  { id: 'dnd5e', label: 'D&D 5e (SRD)' },
]

export function rulesetById(id: string): RulesetDef | undefined {
  return RULESETS.find((ruleset) => ruleset.id === id)
}

export function rulesetLabel(id: string): string {
  return rulesetById(id)?.label ?? id
}
