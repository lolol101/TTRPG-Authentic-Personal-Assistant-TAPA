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

export const SKILLS: { key: string; label: string; ability: AbilityKey }[] = [
  { key: 'acrobatics', label: 'Акробатика', ability: 'dex' },
  { key: 'arcana', label: 'Магия', ability: 'int' },
  { key: 'athletics', label: 'Атлетика', ability: 'str' },
  { key: 'crafting', label: 'Ремесло', ability: 'int' },
  { key: 'deception', label: 'Обман', ability: 'cha' },
  { key: 'diplomacy', label: 'Дипломатия', ability: 'cha' },
  { key: 'intimidation', label: 'Запугивание', ability: 'cha' },
  { key: 'medicine', label: 'Медицина', ability: 'wis' },
  { key: 'nature', label: 'Природа', ability: 'wis' },
  { key: 'occultism', label: 'Оккультизм', ability: 'int' },
  { key: 'performance', label: 'Выступление', ability: 'cha' },
  { key: 'religion', label: 'Религия', ability: 'wis' },
  { key: 'society', label: 'Общество', ability: 'int' },
  { key: 'stealth', label: 'Скрытность', ability: 'dex' },
  { key: 'survival', label: 'Выживание', ability: 'wis' },
  { key: 'thievery', label: 'Воровство', ability: 'dex' },
]

/** PF2e: untrained adds nothing at all — level only counts once trained. */
export function proficiencyBonus(rank: ProficiencyRank, level: number): number {
  if (rank === 'untrained') return 0
  return level + PROFICIENCY_BONUS[rank]
}

export function formatModifier(value: number): string {
  return value >= 0 ? `+${value}` : `${value}`
}
