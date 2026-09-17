import { describe, expect, it } from 'vitest'
import { applyState } from '@/components/ProposedChanges'

describe('applyState', () => {
  it('offers an untouched section', () => {
    expect(applyState('Навыки', [], [])).toBe('idle')
  })

  it('marks the section whose request is in flight', () => {
    expect(applyState('Навыки', [], ['Навыки'])).toBe('applying')
  })

  it('marks every section while "Применить всё" runs', () => {
    expect(applyState('Навыки', [], ['*'])).toBe('applying')
    expect(applyState('Черты', [], ['*'])).toBe('applying')
  })

  it('stays done once applied, so the button keeps its spent state', () => {
    expect(applyState('Навыки', ['Навыки'], [])).toBe('done')
  })

  it('reads the whole-turn marker a reloaded chat carries', () => {
    // The server stores only "this turn was applied", with no record of which
    // sections — a reloaded chat must not hand back live buttons.
    expect(applyState('Навыки', ['*'], [])).toBe('done')
    expect(applyState('Снаряжение', ['*'], [])).toBe('done')
  })

  it('prefers done over applying, so a finished section never flickers back', () => {
    expect(applyState('Навыки', ['Навыки'], ['*'])).toBe('done')
  })

  it('leaves the sections a partial apply did not cover', () => {
    expect(applyState('Черты', ['Навыки'], [])).toBe('idle')
  })
})
