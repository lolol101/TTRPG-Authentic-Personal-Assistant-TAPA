import { createContext, useContext } from 'react'
import type { Character } from '@/lib/api'
import { EMPTY_COMPONENTS, type AbilityKey, type StatComponents } from '@/rulesets/pf2e/domain'
import type { Pf2eSheetData } from '@/rulesets/pf2e/types'

export interface SheetApi {
  draft: Character
  sheet: Pf2eSheetData
  setField: <K extends keyof Character>(key: K, value: Character[K]) => void
  setNumberField: <K extends keyof Character>(key: K, raw: string) => void
  patchSheet: (patch: Partial<Pf2eSheetData>) => void
  componentsFor: (key: string) => StatComponents
  setComponents: (key: string, next: StatComponents) => void
  abilityMod: (ability: AbilityKey) => number
}

const SheetContext = createContext<SheetApi | null>(null)

export const SheetProvider = SheetContext.Provider

export function useSheet(): SheetApi {
  const api = useContext(SheetContext)
  if (!api) throw new Error('useSheet must be used inside the PF2e character sheet')
  return api
}

export function toNumber(raw: string): number {
  const parsed = Number.parseInt(raw, 10)
  return Number.isNaN(parsed) ? 0 : parsed
}

export function componentsOf(sheet: Pf2eSheetData, key: string): StatComponents {
  return sheet.stats?.[key] ?? EMPTY_COMPONENTS
}
