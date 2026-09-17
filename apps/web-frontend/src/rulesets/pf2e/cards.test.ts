import { describe, expect, it } from 'vitest'
import { normalizeInventory } from '@/rulesets/pf2e/cards'

describe('normalizeInventory', () => {
  it('defaults every slot when the sheet has no inventory at all', () => {
    expect(normalizeInventory(undefined)).toEqual({ worn: [], ready: [], other: [] })
  })

  it('leaves a fully populated inventory untouched', () => {
    const worn = [{ name: 'Кольчуга' }]
    const ready = [{ name: 'Кинжал' }]
    const other = [{ name: 'Верёвка' }]

    expect(normalizeInventory({ worn, ready, other })).toEqual({ worn, ready, other })
  })

  it('defaults just the missing slot, not the whole inventory', () => {
    // Observed live: the assistant proposed sheet_data.inventory.worn and
    // .other separately, and "ready" was never touched — the stored object
    // had no "ready" key at all, and inventory.ready.length crashed the tab.
    const worn = [{ name: 'Кожаный доспех' }]
    const other = [{ name: 'Рюкзак' }]

    expect(normalizeInventory({ worn, other })).toEqual({ worn, ready: [], other })
  })
})
