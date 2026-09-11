import { Section } from '@/components/Section'
import { Field } from '@/rulesets/pf2e/components/SheetBits'
import { CardList } from '@/rulesets/pf2e/components/CardList'
import { FEAT_SCHEMA, ITEM_SCHEMA, type Card } from '@/rulesets/pf2e/cards'
import { bulkLimits, COINS } from '@/rulesets/pf2e/domain'
import { toNumber, useSheet } from '@/rulesets/pf2e/sheetContext'

const FEAT_GROUPS = [
  {
    key: 'ancestry_feats' as const,
    title: 'Черты народа и способности',
    hint: 'Особая и родословная на 1 уровне, дальше черты на 1, 5, 9, 13, 17.',
  },
  {
    key: 'class_feats' as const,
    title: 'Классовые черты и способности',
    hint: 'Особенности на нечётных уровнях, черты на чётных.',
  },
  {
    key: 'skill_feats' as const,
    title: 'Черты навыков',
    hint: 'Черта происхождения, дальше на каждом чётном уровне.',
  },
  {
    key: 'general_feats' as const,
    title: 'Общие черты',
    hint: 'На 3, 7, 11, 15 и 19 уровнях.',
  },
  { key: 'bonus_feats' as const, title: 'Дополнительные черты', hint: 'Всё, что не попало выше.' },
]

function ItemColumn({
  title,
  cards,
  onChange,
  hint,
}: {
  title: string
  cards: Card[]
  onChange: (cards: Card[]) => void
  hint?: string
}) {
  return (
    <div className="space-y-1.5">
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{title}</p>
      <CardList schema={ITEM_SCHEMA} cards={cards} onChange={onChange} emptyHint={hint} />
    </div>
  )
}

export function FeatsGearTab() {
  const { draft, sheet, patchSheet } = useSheet()

  const inventory = sheet.inventory ?? { worn: [], ready: [], other: [] }
  const coins = sheet.coins ?? {}
  const limits = bulkLimits(draft.str_mod)

  return (
    <div className="grid gap-3 lg:grid-cols-2">
      {FEAT_GROUPS.map((group) => {
        const cards = sheet[group.key] ?? []
        return (
          <Section
            key={group.key}
            id={`pf2e.${group.key}`}
            title={group.title}
            summary={cards.length ? `${cards.length}` : 'пусто'}
          >
            <CardList
              schema={FEAT_SCHEMA}
              cards={cards}
              onChange={(next) => patchSheet({ [group.key]: next })}
              emptyHint={group.hint}
            />
          </Section>
        )
      })}

      <Section
        id="pf2e.inventory"
        title="Снаряжение"
        className="lg:col-span-2"
        summary={`${inventory.worn.length + inventory.ready.length + inventory.other.length} предм.`}
      >
        <div className="grid gap-4 lg:grid-cols-3">
          <ItemColumn
            title="Носимые предметы"
            cards={inventory.worn}
            onChange={(worn) => patchSheet({ inventory: { ...inventory, worn } })}
            hint="Надето и настроено — не более 10 настроенных предметов."
          />
          <ItemColumn
            title="Готовые предметы"
            cards={inventory.ready}
            onChange={(ready) => patchSheet({ inventory: { ...inventory, ready } })}
            hint="То, что в руках или под рукой."
          />
          <ItemColumn
            title="Прочие предметы"
            cards={inventory.other}
            onChange={(other) => patchSheet({ inventory: { ...inventory, other } })}
            hint="В рюкзаке и на хранении."
          />
        </div>
      </Section>

      <Section
        id="pf2e.bulk"
        title="Вес и монеты"
        className="lg:col-span-2"
        summary={`нагруж. ${limits.encumbered} · макс. ${limits.maximum}`}
      >
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-md border bg-card/60 p-2.5">
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
              Нагруженность
            </p>
            <p className="font-sans text-lg font-semibold tabular-nums">{limits.encumbered}</p>
            <p className="text-[10px] text-muted-foreground">5 + СИЛ</p>
          </div>
          <div className="rounded-md border bg-card/60 p-2.5">
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Максимум</p>
            <p className="font-sans text-lg font-semibold tabular-nums">{limits.maximum}</p>
            <p className="text-[10px] text-muted-foreground">10 + СИЛ</p>
          </div>
          <div className="col-span-2 grid grid-cols-4 gap-2">
            {COINS.map((coin) => (
              <Field
                key={coin.key}
                label={coin.label}
                type="number"
                value={coins[coin.key] ?? 0}
                onChange={(value) => patchSheet({ coins: { ...coins, [coin.key]: toNumber(value) } })}
                inputClassName="text-center font-sans"
              />
            ))}
          </div>
        </div>
      </Section>
    </div>
  )
}
