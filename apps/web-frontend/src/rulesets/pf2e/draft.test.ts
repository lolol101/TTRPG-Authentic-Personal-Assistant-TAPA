import { describe, expect, it } from 'vitest'
import type { Character } from '@/lib/api'
import { draftFrom, initialSheetData, nextDraft } from '@/rulesets/pf2e/draft'

function character(overrides: Partial<Character> = {}): Character {
  return {
    id: 1,
    owner_id: 1,
    name: 'Рэм',
    ancestry: '',
    background: '',
    class_name: '',
    level: 1,
    str_mod: 0,
    dex_mod: 0,
    con_mod: 0,
    int_mod: 0,
    wis_mod: 0,
    cha_mod: 0,
    hp_max: 16,
    hp_current: 16,
    ac: 10,
    speed: 25,
    ruleset: 'pf2e',
    sheet_data: {},
    ...overrides,
  } as Character
}

describe('initialSheetData', () => {
  it('seeds the hp composition from a sheet that only had a total', () => {
    const data = initialSheetData(character({ hp_max: 42, sheet_data: {} }))

    expect(data.hp).toEqual({
      ancestry: 0,
      per_level: 0,
      item: 0,
      other: 42,
      penalty: 0,
      temporary: 0,
    })
  })

  it('leaves a sheet that already has one alone', () => {
    const hp = { ancestry: 8, per_level: 8, item: 0, other: 0, penalty: 0, temporary: 0 }

    expect(initialSheetData(character({ sheet_data: { hp } })).hp).toBe(hp)
  })
})

describe('nextDraft', () => {
  it('follows the stored character while the sheet is untouched', () => {
    // An applied proposal must show in the open sheet, not wait for a reload.
    const current = draftFrom(character({ sheet_data: { languages: '' } }))
    const incoming = character({ sheet_data: { languages: 'общий, эльфийский' } })

    expect(nextDraft(current, incoming, false).sheet_data).toMatchObject({
      languages: 'общий, эльфийский',
    })
  })

  it('keeps unsaved typing rather than overwriting it', () => {
    // Measured before the fix: typing into Языки and stepping into the chat
    // threw the typing away with nothing said. The incoming values are in
    // the database already; the typing exists nowhere else.
    const current = draftFrom(character({ sheet_data: { languages: 'недописанный' } }))
    const incoming = character({ sheet_data: { languages: 'общий, эльфийский' } })

    expect(nextDraft(current, incoming, true)).toBe(current)
  })

  it('starts clean when a different character is opened', () => {
    // Switching characters is not a conflict to protect — it is a new sheet,
    // and carrying the previous one's draft into it would be data from
    // somebody else entirely.
    const current = draftFrom(character({ id: 1, name: 'Рэм' }))
    const incoming = character({ id: 2, name: 'Другой' })

    expect(nextDraft(current, incoming, true).name).toBe('Другой')
    expect(nextDraft(current, incoming, true).id).toBe(2)
  })

  it('gives a fresh object rather than the incoming character itself', () => {
    // The draft is edited in place by the sheet; sharing the object with the
    // App's stored copy would edit that too.
    const incoming = character()

    expect(nextDraft(draftFrom(incoming), incoming, false)).not.toBe(incoming)
  })
})
