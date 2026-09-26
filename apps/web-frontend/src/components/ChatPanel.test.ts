import { describe, expect, it } from 'vitest'
import { rejectedStartsCollapsed } from '@/components/ChatPanel'

describe('rejectedStartsCollapsed', () => {
  it('stays open while nothing from the turn has been taken', () => {
    expect(rejectedStartsCollapsed(false, [])).toBe(false)
    expect(rejectedStartsCollapsed(false, undefined)).toBe(false)
  })

  it('collapses once the whole turn is applied', () => {
    expect(rejectedStartsCollapsed(true, [])).toBe(true)
  })

  it('collapses once even one section is applied, not just the whole turn', () => {
    // A half-applied turn still means the player has looked at this
    // rejection and moved on — leaving it expanded reads as unresolved.
    expect(rejectedStartsCollapsed(false, ['Основное'])).toBe(true)
  })

  it('reads the whole-turn marker a reloaded chat carries', () => {
    expect(rejectedStartsCollapsed(false, ['*'])).toBe(true)
  })
})
