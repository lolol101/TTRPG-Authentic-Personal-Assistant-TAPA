import type { Character } from '@/lib/api'
import type { Pf2eSheetData } from '@/rulesets/pf2e/types'

const DEFAULT_HP = { ancestry: 0, per_level: 0, item: 0, other: 0, penalty: 0, temporary: 0 }

/**
 * Older sheets stored only a flat hp_max. Seeding it into `other` keeps the
 * computed maximum identical while the composition starts out empty.
 */
export function initialSheetData(character: Character): Pf2eSheetData {
  const data = (character.sheet_data ?? {}) as Pf2eSheetData
  if (data.hp) return data
  return { ...data, hp: { ...DEFAULT_HP, other: character.hp_max } }
}

export function draftFrom(character: Character): Character {
  return { ...character, sheet_data: initialSheetData(character) }
}

/**
 * Which draft the sheet should hold once a newer character arrives.
 *
 * The sheet edits a copy and writes it back only when Сохранить is pressed,
 * so two things can move underneath it: the player's own unsaved typing, and
 * the stored character, which the assistant changes whenever a proposal is
 * applied from the chat or a saved version is restored.
 *
 * Untouched, the sheet follows the stored character — otherwise an applied
 * proposal would not show until the page was reloaded. Once there is unsaved
 * typing in it, that typing wins: it exists nowhere else, while the incoming
 * values are safe in the database and one reload away. Overwriting it was
 * the old behaviour, measured: typing into Языки and stepping into the chat
 * threw the typing away with nothing said.
 */
export function nextDraft(current: Character, incoming: Character, dirty: boolean): Character {
  if (dirty && current.id === incoming.id) return current
  return draftFrom(incoming)
}
