/**
 * PF2e rules and vocabulary.
 *
 * Terminology follows the official Russian «Бланк персонажа» (Paizo, 2021):
 * ВЫН not ТЕЛ, Испытания not спасброски, Мистицизм not Магия, ПЗ not ХП,
 * and «умение» for a proficiency rank. Players read the printed sheet, so
 * the app has to speak the same words.
 */

export type AbilityKey = 'str' | 'dex' | 'con' | 'int' | 'wis' | 'cha'

export type ProficiencyRank = 'untrained' | 'trained' | 'expert' | 'master' | 'legendary'

export const PROFICIENCY_RANKS: ProficiencyRank[] = [
  'untrained',
  'trained',
  'expert',
  'master',
  'legendary',
]

export const PROFICIENCY_LABEL: Record<ProficiencyRank, string> = {
  untrained: 'Неизученный',
  trained: 'Изученный',
  expert: 'Экспертный',
  master: 'Мастерский',
  legendary: 'Легендарный',
}

/** The И/Э/М/Л pips printed next to every statistic on the sheet. */
export const PROFICIENCY_SHORT: Record<ProficiencyRank, string> = {
  untrained: '—',
  trained: 'И',
  expert: 'Э',
  master: 'М',
  legendary: 'Л',
}

const PROFICIENCY_BONUS: Record<ProficiencyRank, number> = {
  untrained: 0,
  trained: 2,
  expert: 4,
  master: 6,
  legendary: 8,
}

export const ABILITIES: { key: AbilityKey; label: string; full: string }[] = [
  { key: 'str', label: 'СИЛ', full: 'Сила' },
  { key: 'dex', label: 'ЛВК', full: 'Ловкость' },
  { key: 'con', label: 'ВЫН', full: 'Выносливость' },
  { key: 'int', label: 'ИНТ', full: 'Интеллект' },
  { key: 'wis', label: 'МДР', full: 'Мудрость' },
  { key: 'cha', label: 'ХАР', full: 'Харизма' },
]

export function abilityLabel(key: AbilityKey): string {
  return ABILITIES.find((ability) => ability.key === key)!.label
}

/** «Испытания» on the sheet. */
export const SAVES: { key: string; label: string; ability: AbilityKey }[] = [
  { key: 'fortitude', label: 'Стойкость', ability: 'con' },
  { key: 'reflex', label: 'Реакция', ability: 'dex' },
  { key: 'will', label: 'Воля', ability: 'wis' },
]

const ARMOR_PENALIZED = new Set(['acrobatics', 'athletics', 'stealth', 'thievery'])

export const SKILLS: { key: string; label: string; ability: AbilityKey; armorPenalty: boolean }[] = [
  'acrobatics|Акробатика|dex',
  'athletics|Атлетика|str',
  'thievery|Воровство|dex',
  'survival|Выживание|wis',
  'diplomacy|Дипломатия|cha',
  'intimidation|Запугивание|cha',
  'performance|Исполнение|cha',
  'medicine|Медицина|wis',
  'arcana|Мистицизм|int',
  'deception|Обман|cha',
  'society|Общество|int',
  'occultism|Оккультизм|int',
  'nature|Природа|wis',
  'religion|Религия|wis',
  'crafting|Ремесло|int',
  'stealth|Скрытность|dex',
].map((entry) => {
  const [key, label, ability] = entry.split('|')
  return { key, label, ability: ability as AbilityKey, armorPenalty: ARMOR_PENALIZED.has(key) }
})

export const ARMOR_CATEGORIES: { key: string; label: string }[] = [
  { key: 'unarmored', label: 'Без брони' },
  { key: 'light', label: 'Лёгкая' },
  { key: 'medium', label: 'Средняя' },
  { key: 'heavy', label: 'Тяжёлая' },
]

export const WEAPON_CATEGORIES: { key: string; label: string }[] = [
  { key: 'simple', label: 'Простое' },
  { key: 'unarmed', label: 'Особое' },
  { key: 'martial', label: 'Прочее' },
]

export const SPELL_TRADITIONS: { key: string; label: string }[] = [
  { key: 'arcane', label: 'Мистическая' },
  { key: 'occult', label: 'Оккультная' },
  { key: 'primal', label: 'Первобытная' },
  { key: 'divine', label: 'Сакральная' },
]

export const COINS: { key: string; label: string }[] = [
  { key: 'cp', label: 'ММ' },
  { key: 'sp', label: 'СМ' },
  { key: 'gp', label: 'ЗМ' },
  { key: 'pp', label: 'ПМ' },
]

export interface ConditionDef {
  key: string
  label: string
  valued: boolean
}

export const CONDITIONS: ConditionDef[] = [
  { key: 'blinded', label: 'Ослеплён', valued: false },
  { key: 'clumsy', label: 'Неуклюжий', valued: true },
  { key: 'concealed', label: 'Скрытый частично', valued: false },
  { key: 'confused', label: 'Смущён', valued: false },
  { key: 'controlled', label: 'Под контролем', valued: false },
  { key: 'dazzled', label: 'Ослеплён вспышкой', valued: false },
  { key: 'deafened', label: 'Оглушён', valued: false },
  { key: 'doomed', label: 'Обречён', valued: true },
  { key: 'drained', label: 'Истощён', valued: true },
  { key: 'encumbered', label: 'Перегружен', valued: false },
  { key: 'enfeebled', label: 'Обессилен', valued: true },
  { key: 'fascinated', label: 'Заворожён', valued: false },
  { key: 'fatigued', label: 'Утомлён', valued: false },
  { key: 'fleeing', label: 'Бежит', valued: false },
  { key: 'frightened', label: 'Напуган', valued: true },
  { key: 'grabbed', label: 'Схвачен', valued: false },
  { key: 'hidden', label: 'Спрятан', valued: false },
  { key: 'immobilized', label: 'Обездвижен', valued: false },
  { key: 'invisible', label: 'Невидим', valued: false },
  { key: 'off_guard', label: 'Врасплох', valued: false },
  { key: 'paralyzed', label: 'Парализован', valued: false },
  { key: 'petrified', label: 'Окаменел', valued: false },
  { key: 'prone', label: 'Лежит', valued: false },
  { key: 'quickened', label: 'Ускорен', valued: false },
  { key: 'restrained', label: 'Связан', valued: false },
  { key: 'sickened', label: 'Дурнота', valued: true },
  { key: 'slowed', label: 'Замедлен', valued: true },
  { key: 'stunned', label: 'Ошеломлён', valued: true },
  { key: 'stupefied', label: 'Отупление', valued: true },
  { key: 'unconscious', label: 'Без сознания', valued: false },
  { key: 'wounded', label: 'Ранение', valued: true },
]

/**
 * The Roll20 sheet's core idea, kept here: a statistic is never a bare
 * number, it is a named sum of parts that stay individually editable.
 */
export interface StatComponents {
  rank: ProficiencyRank
  item: number
  temporary: number
}

export const EMPTY_COMPONENTS: StatComponents = { rank: 'untrained', item: 0, temporary: 0 }

/** PF2e: untrained adds nothing at all — level only counts once trained. */
export function proficiencyBonus(rank: ProficiencyRank, level: number): number {
  if (rank === 'untrained') return 0
  return level + PROFICIENCY_BONUS[rank]
}

export interface StatBreakdown {
  total: number
  parts: { label: string; value: number }[]
}

export function computeStat(options: {
  abilityMod: number
  abilityLabel: string
  level: number
  components: StatComponents
  base?: number
  armorPenalty?: number
}): StatBreakdown {
  const { abilityMod, abilityLabel, level, components, base, armorPenalty = 0 } = options
  const proficiency = proficiencyBonus(components.rank, level)

  const parts = [
    ...(base === undefined ? [] : [{ label: 'База', value: base }]),
    { label: abilityLabel, value: abilityMod },
    { label: `Умение (${PROFICIENCY_LABEL[components.rank]})`, value: proficiency },
    { label: 'Предмет', value: components.item },
    { label: 'Временно', value: components.temporary },
    ...(armorPenalty === 0 ? [] : [{ label: 'Броня', value: armorPenalty }]),
  ].filter((part) => part.value !== 0 || part.label === abilityLabel)

  const total =
    (base ?? 0) + abilityMod + proficiency + components.item + components.temporary + armorPenalty

  return { total, parts }
}

/** PF2e max HP: ancestry HP, then class HP plus Con applied at every level. */
export function computeMaxHp(options: {
  ancestry: number
  perLevel: number
  conMod: number
  level: number
  item: number
  other: number
  penalty: number
}): number {
  const { ancestry, perLevel, conMod, level, item, other, penalty } = options
  return ancestry + (perLevel + conMod) * level + item + other - penalty
}

/** Ability score → modifier, as printed on the 2021 sheet. */
export function modifierFromScore(score: number): number {
  return Math.floor((score - 10) / 2)
}

/** Encumbered at 5 + Str, and you cannot carry past 10 + Str. */
export function bulkLimits(strMod: number): { encumbered: number; maximum: number } {
  return { encumbered: 5 + strMod, maximum: 10 + strMod }
}

export function formatModifier(value: number): string {
  return value >= 0 ? `+${value}` : `${value}`
}
