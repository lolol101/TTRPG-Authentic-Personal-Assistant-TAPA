import type { AbilityKey, ProficiencyRank, StatComponents } from '@/rulesets/pf2e/domain'

export interface Strike {
  weapon: string
  components: StatComponents
  damage_dice: string
  damage_ability: string
  damage_type: string
  other: string
  traits: string
}

export interface FeatEntry {
  /** «ЧЕРТА 5», «ОСОБЕННОСТЬ 3» — the printed slot this fills. */
  slot: string
  name: string
}

export interface Item {
  name: string
  invested: boolean
  bulk: string
}

export interface ActionEntry {
  name: string
  actions: string
  traits: string
  page: string
  description: string
}

export interface FreeActionEntry extends ActionEntry {
  kind: 'free' | 'reaction'
  trigger: string
}

export interface SpellEntry {
  name: string
  level: string
  actions: string
  prepared: boolean
}

export interface SpellSlot {
  level: number
  max: number
  remaining: number
}

/**
 * Everything the PF2e sheet needs beyond the shared typed columns.
 *
 * The index signature keeps this assignable to the generic SheetData that
 * the API layer stores, without that layer knowing any PF2e field.
 */
export interface Pf2eSheetData {
  [key: string]: unknown

  player_name?: string
  xp?: number
  heritage?: string
  size?: string
  alignment?: string
  traits?: string
  deity?: string
  languages?: string
  hero_points?: number

  ability_scores?: Partial<Record<AbilityKey, number>>
  stats?: Record<string, StatComponents>

  armor?: { dex_cap: number | null; check_penalty: number }
  armor_proficiencies?: Record<string, ProficiencyRank>
  weapon_proficiencies?: Record<string, ProficiencyRank>
  shield?: { hardness: number; max_hp: number; bt: number; current_hp: number; ac_bonus: number }

  hp?: {
    ancestry: number
    per_level: number
    item: number
    other: number
    penalty: number
    temporary: number
  }
  dying?: number
  wounded?: number
  resistances?: string
  conditions?: Record<string, number>

  senses?: string
  speed_notes?: string
  saves_notes?: string

  melee_strikes?: Strike[]
  ranged_strikes?: Strike[]
  lore?: { name: string; components: StatComponents }[]

  class_dc_ability?: AbilityKey

  ancestry_feats?: FeatEntry[]
  skill_feats?: FeatEntry[]
  general_feats?: FeatEntry[]
  class_feats?: FeatEntry[]
  bonus_feats?: FeatEntry[]

  inventory?: { worn: Item[]; ready: Item[]; other: Item[] }
  coins?: Record<string, number>

  bio?: {
    ethnicity?: string
    nationality?: string
    birthplace?: string
    age?: string
    gender?: string
    height?: string
    weight?: string
    appearance?: string
  }
  personality?: {
    attitude?: string
    beliefs?: string
    likes?: string
    dislikes?: string
    catchphrases?: string
  }
  campaign?: { notes?: string; allies?: string; enemies?: string; organizations?: string }

  actions?: ActionEntry[]
  free_actions?: FreeActionEntry[]

  spellcasting?: {
    tradition?: string
    prepared?: boolean
    key_ability?: AbilityKey
    attack?: StatComponents
    dc?: StatComponents
    slots?: SpellSlot[]
    focus_points?: { current: number; max: number }
  }
  spells?: SpellEntry[]
  focus_spells?: SpellEntry[]
  innate_spells?: SpellEntry[]

  notes?: string
}

export const EMPTY_STRIKE: Strike = {
  weapon: '',
  components: { rank: 'untrained', item: 0, temporary: 0 },
  damage_dice: '',
  damage_ability: '',
  damage_type: '',
  other: '',
  traits: '',
}

export const EMPTY_ITEM: Item = { name: '', invested: false, bulk: '' }

export const EMPTY_ACTION: ActionEntry = {
  name: '',
  actions: '',
  traits: '',
  page: '',
  description: '',
}

export const EMPTY_FREE_ACTION: FreeActionEntry = { ...EMPTY_ACTION, kind: 'free', trigger: '' }

export const EMPTY_SPELL: SpellEntry = { name: '', level: '', actions: '', prepared: false }
