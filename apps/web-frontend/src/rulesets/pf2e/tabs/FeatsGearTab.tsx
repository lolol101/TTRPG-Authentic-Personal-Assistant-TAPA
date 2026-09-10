import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import {
  Field,
  FixedSlotList,
  RepeatingList,
  SectionTitle,
} from '@/rulesets/pf2e/components/SheetBits'
import { bulkLimits, COINS } from '@/rulesets/pf2e/domain'
import { toNumber, useSheet } from '@/rulesets/pf2e/sheetContext'
import { EMPTY_ITEM, type FeatEntry, type Item } from '@/rulesets/pf2e/types'

const ANCESTRY_SLOTS = ['Особая 1', 'Родословная 1', 'Черта 1', 'Черта 5', 'Черта 9', 'Черта 13', 'Черта 17']
const SKILL_FEAT_SLOTS = ['Происхождение', '2', '4', '6', '8', '10', '12', '14', '16', '18', '20']
const GENERAL_FEAT_SLOTS = ['3', '7', '11', '15', '19']
const CLASS_SLOTS = [
  'Особенность 1',
  'Особенность 1 (2)',
  'Черта 1',
  'Черта 2',
  'Особенность 3',
  'Черта 4',
  'Особенность 5',
  'Черта 6',
  'Особенность 7',
  'Черта 8',
  'Особенность 9',
  'Черта 10',
  'Особенность 11',
  'Черта 12',
  'Особенность 13',
  'Черта 14',
  'Особенность 15',
  'Черта 16',
  'Особенность 17',
  'Черта 18',
  'Особенность 19',
  'Черта 20',
]

function ItemColumn({
  title,
  items,
  onChange,
  showInvested,
}: {
  title: string
  items: Item[]
  onChange: (items: Item[]) => void
  showInvested?: boolean
}) {
  return (
    <div className="space-y-2">
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{title}</p>
      <RepeatingList
        items={items}
        onChange={onChange}
        blank={EMPTY_ITEM}
        addLabel="Добавить предмет"
        renderRow={(item, update) => (
          <div className="flex flex-wrap items-end gap-2">
            <Field
              label="Предмет"
              value={item.name}
              onChange={(name) => update({ ...item, name })}
              className="min-w-32 flex-1"
            />
            <Field
              label="Вес"
              value={item.bulk}
              onChange={(bulk) => update({ ...item, bulk })}
              className="w-16"
            />
            {showInvested && (
              <label className="flex h-8 items-center gap-1.5 text-[10px] uppercase text-muted-foreground">
                <input
                  type="checkbox"
                  checked={item.invested}
                  onChange={(event) => update({ ...item, invested: event.target.checked })}
                />
                Настр.
              </label>
            )}
          </div>
        )}
      />
    </div>
  )
}

function FeatSection({
  title,
  slots,
  entries,
  onChange,
}: {
  title: string
  slots: string[]
  entries: FeatEntry[]
  onChange: (entries: FeatEntry[]) => void
}) {
  return (
    <Card>
      <CardHeader>
        <SectionTitle>{title}</SectionTitle>
      </CardHeader>
      <CardContent>
        <FixedSlotList slots={slots} entries={entries} onChange={onChange} />
      </CardContent>
    </Card>
  )
}

export function FeatsGearTab() {
  const { draft, sheet, patchSheet } = useSheet()

  const inventory = sheet.inventory ?? { worn: [], ready: [], other: [] }
  const coins = sheet.coins ?? {}
  const limits = bulkLimits(draft.str_mod)

  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-4">
          <FeatSection
            title="Черты народа и способности"
            slots={ANCESTRY_SLOTS}
            entries={sheet.ancestry_feats ?? []}
            onChange={(ancestry_feats) => patchSheet({ ancestry_feats })}
          />
          <FeatSection
            title="Черты навыков"
            slots={SKILL_FEAT_SLOTS}
            entries={sheet.skill_feats ?? []}
            onChange={(skill_feats) => patchSheet({ skill_feats })}
          />
          <FeatSection
            title="Общие черты"
            slots={GENERAL_FEAT_SLOTS}
            entries={sheet.general_feats ?? []}
            onChange={(general_feats) => patchSheet({ general_feats })}
          />
        </div>

        <div className="space-y-4">
          <FeatSection
            title="Классовые черты и способности"
            slots={CLASS_SLOTS}
            entries={sheet.class_feats ?? []}
            onChange={(class_feats) => patchSheet({ class_feats })}
          />
          <Card>
            <CardHeader>
              <SectionTitle>Дополнительные черты</SectionTitle>
            </CardHeader>
            <CardContent>
              <RepeatingList
                items={sheet.bonus_feats ?? []}
                onChange={(bonus_feats) => patchSheet({ bonus_feats })}
                blank={{ slot: 'доп.', name: '' }}
                addLabel="Добавить черту"
                renderRow={(entry, update) => (
                  <Field
                    label="Черта"
                    value={entry.name}
                    onChange={(name) => update({ ...entry, name })}
                  />
                )}
              />
            </CardContent>
          </Card>
        </div>
      </div>

      <Card>
        <CardHeader>
          <SectionTitle>Снаряжение</SectionTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-3">
            <ItemColumn
              title="Носимые предметы (настр. макс. 10)"
              items={inventory.worn}
              onChange={(worn) => patchSheet({ inventory: { ...inventory, worn } })}
              showInvested
            />
            <ItemColumn
              title="Готовые предметы"
              items={inventory.ready}
              onChange={(ready) => patchSheet({ inventory: { ...inventory, ready } })}
            />
            <ItemColumn
              title="Прочие предметы"
              items={inventory.other}
              onChange={(other) => patchSheet({ inventory: { ...inventory, other } })}
            />
          </div>

          <Separator />

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
        </CardContent>
      </Card>
    </div>
  )
}
