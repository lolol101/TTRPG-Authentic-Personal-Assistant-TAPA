/**
 * Field layouts for the sheet's content cards.
 *
 * A feat, an item and a spell each have a real stat block in the book, not
 * just a name: level, traits, requirements, bulk, price and so on. These
 * schemas mirror the official structure — see «Reading Items» and «Reading
 * Spells» on Archives of Nethys, and the card markup on pf2.ru.
 *
 * Filled in by hand for now; a catalog that auto-fills them is its own
 * backlog item, which is why every card carries a source field.
 */

export type FieldKind = 'text' | 'number' | 'textarea' | 'select' | 'checkbox'

export interface CardField {
  key: string
  label: string
  kind: FieldKind
  options?: string[]
  /** Shown on the collapsed row, so a closed card still says something. */
  summary?: boolean
  /** Take the whole row rather than a grid cell. */
  wide?: boolean
}

export interface CardSchema {
  addLabel: string
  fields: CardField[]
}

const RARITY = ['обычный', 'необычный', 'редкий', 'уникальный']

const SOURCE_FIELD: CardField = { key: 'source', label: 'Источник', kind: 'text' }
const DESCRIPTION_FIELD: CardField = {
  key: 'description',
  label: 'Описание',
  kind: 'textarea',
  wide: true,
}

export const ITEM_SCHEMA: CardSchema = {
  addLabel: 'Добавить предмет',
  fields: [
    { key: 'name', label: 'Название', kind: 'text', summary: true, wide: true },
    { key: 'level', label: 'Уровень', kind: 'number', summary: true },
    { key: 'price', label: 'Цена', kind: 'text', summary: true },
    { key: 'bulk', label: 'Вес', kind: 'text', summary: true },
    { key: 'quantity', label: 'Количество', kind: 'number' },
    { key: 'usage', label: 'Применение', kind: 'text' },
    { key: 'hands', label: 'Руки', kind: 'text' },
    { key: 'rarity', label: 'Редкость', kind: 'select', options: RARITY },
    { key: 'traits', label: 'Дескрипторы', kind: 'text', wide: true },
    { key: 'invested', label: 'Настроен', kind: 'checkbox' },
    { key: 'activate', label: 'Активация', kind: 'text' },
    { key: 'frequency', label: 'Частота', kind: 'text' },
    { key: 'trigger', label: 'Триггер', kind: 'text' },
    { key: 'requirements', label: 'Требования', kind: 'text' },
    SOURCE_FIELD,
    DESCRIPTION_FIELD,
  ],
}

export const FEAT_SCHEMA: CardSchema = {
  addLabel: 'Добавить черту',
  fields: [
    { key: 'name', label: 'Название', kind: 'text', summary: true, wide: true },
    { key: 'level', label: 'Уровень', kind: 'number', summary: true },
    { key: 'slot', label: 'Слот бланка', kind: 'text', summary: true },
    { key: 'actions', label: 'Действия', kind: 'text', summary: true },
    { key: 'rarity', label: 'Редкость', kind: 'select', options: RARITY },
    { key: 'traits', label: 'Дескрипторы', kind: 'text', wide: true },
    { key: 'prerequisites', label: 'Предварительные условия', kind: 'text', wide: true },
    { key: 'frequency', label: 'Частота', kind: 'text' },
    { key: 'trigger', label: 'Триггер', kind: 'text' },
    { key: 'requirements', label: 'Требования', kind: 'text' },
    SOURCE_FIELD,
    DESCRIPTION_FIELD,
    { key: 'special', label: 'Особое', kind: 'textarea', wide: true },
  ],
}

export const SPELL_SCHEMA: CardSchema = {
  addLabel: 'Добавить заклинание',
  fields: [
    { key: 'name', label: 'Название', kind: 'text', summary: true, wide: true },
    // Key stays `level` so sheets saved before cards existed still read.
    { key: 'level', label: 'Круг', kind: 'text', summary: true },
    { key: 'actions', label: 'Сотворение', kind: 'text', summary: true },
    { key: 'prepared', label: 'Подготовлено', kind: 'checkbox', summary: true },
    { key: 'rarity', label: 'Редкость', kind: 'select', options: RARITY },
    { key: 'traditions', label: 'Традиции', kind: 'text' },
    { key: 'traits', label: 'Дескрипторы', kind: 'text', wide: true },
    { key: 'components', label: 'Компоненты', kind: 'text' },
    { key: 'range', label: 'Дистанция', kind: 'text' },
    { key: 'area', label: 'Область', kind: 'text' },
    { key: 'targets', label: 'Цели', kind: 'text' },
    { key: 'save', label: 'Защита', kind: 'text' },
    { key: 'duration', label: 'Длительность', kind: 'text' },
    SOURCE_FIELD,
    DESCRIPTION_FIELD,
    { key: 'heightened', label: 'Повышение', kind: 'textarea', wide: true },
  ],
}

export type CardValue = string | number | boolean | undefined
export type Card = Record<string, CardValue>

export function blankCard(schema: CardSchema): Card {
  const card: Card = {}
  for (const field of schema.fields) {
    card[field.key] = field.kind === 'checkbox' ? false : field.kind === 'number' ? 0 : ''
  }
  return card
}

/** The one-line preview shown while a card is collapsed. */
export function cardSummary(schema: CardSchema, card: Card): string {
  return schema.fields
    .filter((field) => field.summary && field.key !== 'name')
    .map((field) => {
      const value = card[field.key]
      if (value === '' || value === undefined || value === false || value === 0) return null
      if (field.kind === 'checkbox') return field.label
      return `${field.label} ${value}`
    })
    .filter(Boolean)
    .join(' · ')
}
