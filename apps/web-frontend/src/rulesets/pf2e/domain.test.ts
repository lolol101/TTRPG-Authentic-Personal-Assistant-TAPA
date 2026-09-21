import { describe, expect, it } from 'vitest'
import {
  bulkLimits,
  computeMaxHp,
  computeStat,
  modifierFromScore,
  normalizeComponents,
  proficiencyBonus,
  scoreForModifier,
  scoreFromModifier,
  type StatComponents,
} from '@/rulesets/pf2e/domain'

const NONE: StatComponents = { rank: 'untrained', item: 0, temporary: 0 }

describe('proficiencyBonus', () => {
  it('gives untrained nothing at all, not even level', () => {
    expect(proficiencyBonus('untrained', 12)).toBe(0)
  })

  it('adds level once trained', () => {
    expect(proficiencyBonus('trained', 1)).toBe(3)
    expect(proficiencyBonus('expert', 3)).toBe(7)
    expect(proficiencyBonus('master', 10)).toBe(16)
    expect(proficiencyBonus('legendary', 20)).toBe(28)
  })
})

describe('computeStat', () => {
  it('sums ability, proficiency, item and temporary', () => {
    const { total } = computeStat({
      abilityMod: 4,
      abilityLabel: 'СИЛ',
      level: 3,
      components: { rank: 'expert', item: 1, temporary: 2 },
    })
    expect(total).toBe(4 + 7 + 1 + 2)
  })

  it('adds the base for AC and class DC', () => {
    const { total } = computeStat({
      abilityMod: 2,
      abilityLabel: 'ЛОВ',
      level: 1,
      components: { rank: 'trained', item: 2, temporary: 0 },
      base: 10,
    })
    expect(total).toBe(10 + 2 + 3 + 2)
  })

  it('subtracts an armor check penalty', () => {
    const { total } = computeStat({
      abilityMod: 3,
      abilityLabel: 'СИЛ',
      level: 5,
      components: { rank: 'trained', item: 0, temporary: 0 },
      armorPenalty: -2,
    })
    expect(total).toBe(3 + 7 - 2)
  })

  it('leaves an untrained skill at just its ability modifier', () => {
    const { total } = computeStat({
      abilityMod: -1,
      abilityLabel: 'ИНТ',
      level: 8,
      components: NONE,
    })
    expect(total).toBe(-1)
  })

  it('keeps the ability part visible even at +0, and hides empty parts', () => {
    const { parts } = computeStat({
      abilityMod: 0,
      abilityLabel: 'МДР',
      level: 2,
      components: { rank: 'trained', item: 0, temporary: 0 },
    })
    expect(parts.map((part) => part.label)).toEqual(['МДР', 'Умение (Изученный)'])
  })
})

describe('computeMaxHp', () => {
  it('applies class HP and Constitution at every level', () => {
    // Human fighter: 8 ancestry, 10/level, +3 Con, level 5.
    expect(
      computeMaxHp({ ancestry: 8, perLevel: 10, conMod: 3, level: 5, item: 0, other: 0, penalty: 0 }),
    ).toBe(8 + 13 * 5)
  })

  it('adds item and other bonuses and subtracts penalties', () => {
    expect(
      computeMaxHp({ ancestry: 8, perLevel: 6, conMod: 1, level: 2, item: 4, other: 3, penalty: 5 }),
    ).toBe(8 + 7 * 2 + 4 + 3 - 5)
  })

  it('reduces to the carried-over total when no composition is filled in', () => {
    expect(
      computeMaxHp({ ancestry: 0, perLevel: 0, conMod: 0, level: 3, item: 0, other: 45, penalty: 0 }),
    ).toBe(45)
  })
})

describe('modifierFromScore', () => {
  it('follows the sheet: (значение - 10) / 2, rounded down', () => {
    expect(modifierFromScore(18)).toBe(4)
    expect(modifierFromScore(10)).toBe(0)
    expect(modifierFromScore(11)).toBe(0)
  })

  it('rounds odd low scores down, not toward zero', () => {
    expect(modifierFromScore(9)).toBe(-1)
    expect(modifierFromScore(7)).toBe(-2)
  })
})

describe('scoreFromModifier', () => {
  it('walks back the sheet: two points of score per point of modifier', () => {
    expect(scoreFromModifier(1)).toBe(12)
    expect(scoreFromModifier(2)).toBe(14)
    expect(scoreFromModifier(0)).toBe(10)
    expect(scoreFromModifier(4)).toBe(18)
  })

  it('goes below ten for a penalty', () => {
    expect(scoreFromModifier(-1)).toBe(8)
  })

  it('round-trips through modifierFromScore', () => {
    for (const modifier of [-2, -1, 0, 1, 2, 3, 4, 5, 6]) {
      expect(modifierFromScore(scoreFromModifier(modifier))).toBe(modifier)
    }
  })
})

describe('scoreForModifier', () => {
  it('rewrites a score that contradicts the typed modifier', () => {
    expect(scoreForModifier(2, 10)).toBe(14)
    expect(scoreForModifier(0, 18)).toBe(10)
  })

  it('leaves an odd score that already produces that modifier alone', () => {
    // 13 is +1 just as much as 12 is; retyping +1 must not shave a point off
    // a score the player entered deliberately.
    expect(scoreForModifier(1, 13)).toBe(13)
    expect(scoreForModifier(-1, 9)).toBe(9)
  })

  it('leaves an already-matching even score alone', () => {
    expect(scoreForModifier(2, 14)).toBe(14)
  })
})

describe('bulkLimits', () => {
  it('encumbers at 5 + Str and caps at 10 + Str', () => {
    expect(bulkLimits(3)).toEqual({ encumbered: 8, maximum: 13 })
    expect(bulkLimits(-1)).toEqual({ encumbered: 4, maximum: 9 })
  })
})

describe('normalizeComponents', () => {
  it('defaults every part when the sheet has nothing for this stat', () => {
    expect(normalizeComponents(undefined)).toEqual({ rank: 'untrained', item: 0, temporary: 0 })
  })

  it('leaves a fully populated component set untouched', () => {
    const full: StatComponents = { rank: 'expert', item: 1, temporary: 2 }
    expect(normalizeComponents(full)).toEqual(full)
  })

  it('defaults just the missing parts, not the whole component set', () => {
    // Observed live: rank, item and temporary are proposed and written
    // independently, same as inventory slots — a stat whose item/temporary
    // bonus was never touched stored only { rank: "trained" }, and
    // computeStat's `+ components.item + components.temporary` turned every
    // such skill into NaN.
    expect(normalizeComponents({ rank: 'trained' })).toEqual({
      rank: 'trained',
      item: 0,
      temporary: 0,
    })
  })

  it('keeps a stat total finite once normalized', () => {
    const { total } = computeStat({
      abilityMod: 3,
      abilityLabel: 'СИЛ',
      level: 5,
      components: normalizeComponents({ rank: 'trained' }),
    })
    expect(Number.isNaN(total)).toBe(false)
  })
})
