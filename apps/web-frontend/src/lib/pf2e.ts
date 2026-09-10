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
  untrained: 'Нетренирован',
  trained: 'Тренирован',
  expert: 'Эксперт',
  master: 'Мастер',
  legendary: 'Легенда',
}

export const PROFICIENCY_SHORT: Record<ProficiencyRank, string> = {
  untrained: 'Н',
  trained: 'Т',
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
  { key: 'dex', label: 'ЛОВ', full: 'Ловкость' },
  { key: 'con', label: 'ТЕЛ', full: 'Телосложение' },
  { key: 'int', label: 'ИНТ', full: 'Интеллект' },
  { key: 'wis', label: 'МДР', full: 'Мудрость' },
  { key: 'cha', label: 'ХАР', full: 'Харизма' },
]

export const SAVES: { key: string; label: string; ability: AbilityKey }[] = [
  { key: 'fortitude', label: 'Стойкость', ability: 'con' },
  { key: 'reflex', label: 'Реакция', ability: 'dex' },
  { key: 'will', label: 'Воля', ability: 'wis' },
]

/** Skills that armor's check penalty applies to (PF2e: Str- and Dex-based). */
const ARMOR_PENALIZED = new Set(['acrobatics', 'athletics', 'stealth', 'thievery'])

export const SKILLS: { key: string; label: string; ability: AbilityKey; armorPenalty: boolean }[] = [
  'acrobatics|Акробатика|dex',
  'arcana|Магия|int',
  'athletics|Атлетика|str',
  'crafting|Ремесло|int',
  'deception|Обман|cha',
  'diplomacy|Дипломатия|cha',
  'intimidation|Запугивание|cha',
  'medicine|Медицина|wis',
  'nature|Природа|wis',
  'occultism|Оккультизм|int',
  'performance|Выступление|cha',
  'religion|Религия|wis',
  'society|Общество|int',
  'stealth|Скрытность|dex',
  'survival|Выживание|wis',
  'thievery|Воровство|dex',
].map((entry) => {
  const [key, label, ability] = entry.split('|')
  return { key, label, ability: ability as AbilityKey, armorPenalty: ARMOR_PENALIZED.has(key) }
})

export interface ConditionDef {
  key: string
  label: string
  valued: boolean
}

/** PF2e conditions, mirroring the toggle/value split on the Roll20 sheet. */
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
  { key: 'dying', label: 'Умирает', valued: true },
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
  { key: 'stunned', label: 'Оглушён (шок)', valued: true },
  { key: 'stupefied', label: 'Отупление', valued: true },
  { key: 'unconscious', label: 'Без сознания', valued: false },
  { key: 'wounded', label: 'Ранен', valued: true },
]

/**
 * The Roll20 sheet's core idea: a statistic is never a bare number, it is a
 * named sum of parts that stay individually editable.
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
    { label: `Владение (${PROFICIENCY_LABEL[components.rank]})`, value: proficiency },
    { label: 'Предмет', value: components.item },
    { label: 'Временно', value: components.temporary },
    ...(armorPenalty === 0 ? [] : [{ label: 'Штраф брони', value: armorPenalty }]),
  ].filter((part) => part.value !== 0 || part.label === abilityLabel)

  const total =
    (base ?? 0) + abilityMod + proficiency + components.item + components.temporary + armorPenalty

  return { total, parts }
}

/**
 * PF2e max HP: ancestry HP, then class HP plus Con applied at every level.
 */
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

export function formatModifier(value: number): string {
  return value >= 0 ? `+${value}` : `${value}`
}
