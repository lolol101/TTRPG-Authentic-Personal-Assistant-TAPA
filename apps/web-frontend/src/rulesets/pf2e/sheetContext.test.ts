import { describe, expect, it } from 'vitest'
import { componentsOf, toNumber } from '@/rulesets/pf2e/sheetContext'
import type { Pf2eSheetData } from '@/rulesets/pf2e/types'

describe('componentsOf', () => {
  it('defaults every part when the sheet has no stats at all', () => {
    expect(componentsOf({} as Pf2eSheetData, 'stealth')).toEqual({
      rank: 'untrained',
      item: 0,
      temporary: 0,
    })
  })

  it('defaults just the missing parts of a partially written stat', () => {
    // The same bug this file's componentsOf duplicated: a stat proposed and
    // applied one field at a time can be stored with only `rank`.
    const sheet = { stats: { stealth: { rank: 'trained' } } } as unknown as Pf2eSheetData

    expect(componentsOf(sheet, 'stealth')).toEqual({ rank: 'trained', item: 0, temporary: 0 })
  })
})

describe('toNumber', () => {
  it('parses a plain integer', () => {
    expect(toNumber('12')).toBe(12)
  })

  it('falls back to zero rather than NaN on unparseable input', () => {
    expect(toNumber('')).toBe(0)
    expect(toNumber('abc')).toBe(0)
  })
})
