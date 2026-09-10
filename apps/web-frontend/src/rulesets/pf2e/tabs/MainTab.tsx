import { Section } from '@/components/Section'
import { Input } from '@/components/ui/input'
import { Separator } from '@/components/ui/separator'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import {
  BigNumber,
  Field,
  LabeledRankRow,
  RepeatingList,
  SectionTitle,
} from '@/rulesets/pf2e/components/SheetBits'
import { StatRow } from '@/rulesets/pf2e/components/StatRow'
import {
  ABILITIES,
  abilityLabel,
  ARMOR_CATEGORIES,
  computeMaxHp,
  CONDITIONS,
  EMPTY_COMPONENTS,
  formatModifier,
  modifierFromScore,
  SAVES,
  SKILLS,
  WEAPON_CATEGORIES,
  type ProficiencyRank,
} from '@/rulesets/pf2e/domain'
import { toNumber, useSheet } from '@/rulesets/pf2e/sheetContext'
import { EMPTY_STRIKE, type Strike } from '@/rulesets/pf2e/types'

const DEFAULT_HP = { ancestry: 0, per_level: 0, item: 0, other: 0, penalty: 0, temporary: 0 }

function StrikeBlock({
  id,
  title,
  ability,
  items,
  onChange,
  otherLabel,
}: {
  id: string
  title: string
  ability: 'str' | 'dex'
  items: Strike[]
  onChange: (items: Strike[]) => void
  otherLabel: string
}) {
  const { draft, abilityMod } = useSheet()

  return (
    <Section
      id={id}
      title={title}
      className="lg:col-span-2"
      summary={items.length ? items.map((strike) => strike.weapon || '—').join(', ') : 'пусто'}
    >
      <RepeatingList
        items={items}
        onChange={onChange}
        blank={EMPTY_STRIKE}
        addLabel="Добавить оружие"
        renderRow={(strike, update) => (
          <div className="space-y-2">
            <div className="flex flex-wrap items-end gap-2">
              <Field
                label="Оружие"
                value={strike.weapon}
                onChange={(value) => update({ ...strike, weapon: value })}
                className="min-w-40 flex-1"
              />
              <StatRow
                label="Атака"
                abilityLabel={abilityLabel(ability)}
                abilityMod={abilityMod(ability)}
                level={draft.level}
                components={strike.components}
                onChange={(components) => update({ ...strike, components })}
                className="min-w-56 flex-1"
              />
            </div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
              <Field
                label="Кость урона"
                value={strike.damage_dice}
                onChange={(value) => update({ ...strike, damage_dice: value })}
              />
              <Field
                label={otherLabel}
                value={strike.damage_ability}
                onChange={(value) => update({ ...strike, damage_ability: value })}
              />
              <Field
                label="Тип (Д/К/Р)"
                value={strike.damage_type}
                onChange={(value) => update({ ...strike, damage_type: value })}
              />
              <Field
                label="Прочее"
                value={strike.other}
                onChange={(value) => update({ ...strike, other: value })}
              />
              <Field
                label="Дескрипторы"
                value={strike.traits}
                onChange={(value) => update({ ...strike, traits: value })}
              />
            </div>
          </div>
        )}
      />
    </Section>
  )
}

export function MainTab() {
  const {
    draft,
    sheet,
    setField,
    setNumberField,
    patchSheet,
    componentsFor,
    setComponents,
    abilityMod,
  } = useSheet()

  const hp = sheet.hp ?? DEFAULT_HP
  const conditions = sheet.conditions ?? {}
  const armor = sheet.armor ?? { dex_cap: null, check_penalty: 0 }
  const armorPenalty = armor.check_penalty ?? 0
  const shield = sheet.shield ?? { hardness: 0, max_hp: 0, bt: 0, current_hp: 0, ac_bonus: 0 }
  const scores = sheet.ability_scores ?? {}
  const cappedDex = armor.dex_cap === null ? draft.dex_mod : Math.min(draft.dex_mod, armor.dex_cap)
  const classDcAbility = sheet.class_dc_ability ?? 'str'
  const heroPoints = sheet.hero_points ?? 0

  const maxHp = computeMaxHp({
    ancestry: hp.ancestry,
    perLevel: hp.per_level,
    conMod: draft.con_mod,
    level: draft.level,
    item: hp.item,
    other: hp.other,
    penalty: hp.penalty,
  })

  const activeConditions = Object.entries(conditions).filter(([, value]) => value)

  function setHp(key: keyof typeof DEFAULT_HP, raw: string) {
    patchSheet({ hp: { ...hp, [key]: toNumber(raw) } })
  }

  function toggleCondition(key: string, valued: boolean) {
    const current = conditions[key] ?? 0
    const next = { ...conditions }
    if (valued) {
      const raised = current + 1
      if (raised > 4) delete next[key]
      else next[key] = raised
    } else if (current) {
      delete next[key]
    } else {
      next[key] = 1
    }
    patchSheet({ conditions: next })
  }

  function setRank(
    group: 'armor_proficiencies' | 'weapon_proficiencies',
    key: string,
    rank: ProficiencyRank,
  ) {
    patchSheet({ [group]: { ...(sheet[group] ?? {}), [key]: rank } })
  }

  return (
    <div className="grid gap-3 lg:grid-cols-2">
      <Section
        id="pf2e.identity"
        title="Персонаж"
        defaultOpen
        className="lg:col-span-2"
        summary={`${draft.name || 'без имени'} · ${draft.level} ур.`}
      >
        <div className="space-y-3">
          <div className="grid gap-3 md:grid-cols-[2fr_1fr_1fr]">
            <label className="block space-y-1">
              <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                Имя персонажа
              </span>
              <Input
                value={draft.name}
                onChange={(event) => setField('name', event.target.value)}
                className="font-heading h-12 text-2xl"
              />
            </label>
            <div className="grid grid-cols-2 gap-2">
              <Field
                label="Уровень"
                type="number"
                value={draft.level}
                onChange={(value) => setNumberField('level', value)}
                inputClassName="h-12 text-center font-sans text-xl font-semibold"
              />
              <Field
                label="Опыт"
                type="number"
                value={sheet.xp ?? 0}
                onChange={(value) => patchSheet({ xp: toNumber(value) })}
                inputClassName="h-12 text-center font-sans text-xl"
              />
            </div>
            <div className="space-y-1">
              <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                Пункты героизма
              </span>
              <div className="flex gap-1.5 pt-1.5">
                {[1, 2, 3].map((point) => (
                  <button
                    key={point}
                    type="button"
                    onClick={() => patchSheet({ hero_points: heroPoints === point ? 0 : point })}
                    className={cn(
                      'size-8 rounded-full border-2 transition-colors',
                      point <= heroPoints ? 'border-primary bg-primary' : 'border-muted-foreground/40',
                    )}
                  />
                ))}
              </div>
            </div>
          </div>

          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            <Field
              label="Имя игрока"
              value={sheet.player_name ?? ''}
              onChange={(v) => patchSheet({ player_name: v })}
            />
            <Field label="Народ" value={draft.ancestry} onChange={(v) => setField('ancestry', v)} />
            <Field
              label="Родословная"
              value={sheet.heritage ?? ''}
              onChange={(v) => patchSheet({ heritage: v })}
            />
            <Field
              label="Происхождение"
              value={draft.background}
              onChange={(v) => setField('background', v)}
            />
            <Field label="Класс" value={draft.class_name} onChange={(v) => setField('class_name', v)} />
            <Field label="Размер" value={sheet.size ?? ''} onChange={(v) => patchSheet({ size: v })} />
            <Field
              label="Мировоззрение"
              value={sheet.alignment ?? ''}
              onChange={(v) => patchSheet({ alignment: v })}
            />
            <Field
              label="Дескрипторы"
              value={sheet.traits ?? ''}
              onChange={(v) => patchSheet({ traits: v })}
            />
            <Field label="Божество" value={sheet.deity ?? ''} onChange={(v) => patchSheet({ deity: v })} />
          </div>
        </div>
      </Section>

      <Section
        id="pf2e.abilities"
        title="Характеристики"
        defaultOpen
        className="lg:col-span-2"
        summary={ABILITIES.map(
          (ability) => `${ability.label} ${formatModifier(abilityMod(ability.key))}`,
        ).join(' · ')}
      >
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {ABILITIES.map((ability) => {
            const score = scores[ability.key] ?? 10
            return (
              <div key={ability.key} className="space-y-1.5 rounded-md border bg-card/60 p-2.5">
                <div className="text-center text-xs font-semibold" title={ability.full}>
                  {ability.label}
                </div>
                <Field
                  label="Модификатор"
                  type="number"
                  value={draft[`${ability.key}_mod` as const]}
                  onChange={(value) => setNumberField(`${ability.key}_mod` as const, value)}
                  inputClassName="h-10 text-center font-sans text-lg font-semibold"
                />
                <Field
                  label="Значение"
                  type="number"
                  value={score}
                  onChange={(value) =>
                    patchSheet({ ability_scores: { ...scores, [ability.key]: toNumber(value) } })
                  }
                  inputClassName="text-center font-sans"
                />
                <p className="text-center text-[10px] text-muted-foreground">
                  по значению {formatModifier(modifierFromScore(score))}
                </p>
              </div>
            )
          })}
        </div>
      </Section>

      <Section id="pf2e.ac" title="Класс брони и щит" defaultOpen summary={`КБ ${draft.ac}`}>
        <div className="space-y-3">
          <StatRow
            label="Класс брони"
            abilityLabel="ЛВК"
            abilityMod={cappedDex}
            level={draft.level}
            base={10}
            components={componentsFor('armor_class')}
            onChange={(next) => setComponents('armor_class', next)}
            hint={armor.dex_cap === null ? undefined : `макс. ЛВК ${formatModifier(armor.dex_cap)}`}
          />
          <div className="grid grid-cols-2 gap-2">
            <Field
              label="Макс. ЛВК от брони"
              type="number"
              value={armor.dex_cap ?? ''}
              onChange={(value) =>
                patchSheet({ armor: { ...armor, dex_cap: value === '' ? null : toNumber(value) } })
              }
            />
            <Field
              label="Штраф проверок"
              type="number"
              value={armorPenalty}
              onChange={(value) =>
                patchSheet({ armor: { ...armor, check_penalty: toNumber(value) } })
              }
            />
          </div>

          <Separator />

          <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Щит</p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Field
              label="Бонус КБ"
              type="number"
              value={shield.ac_bonus}
              onChange={(v) => patchSheet({ shield: { ...shield, ac_bonus: toNumber(v) } })}
            />
            <Field
              label="Твёрдость"
              type="number"
              value={shield.hardness}
              onChange={(v) => patchSheet({ shield: { ...shield, hardness: toNumber(v) } })}
            />
            <Field
              label="Макс. ПЗ"
              type="number"
              value={shield.max_hp}
              onChange={(v) => patchSheet({ shield: { ...shield, max_hp: toNumber(v) } })}
            />
            <Field
              label="ПП"
              type="number"
              value={shield.bt}
              onChange={(v) => patchSheet({ shield: { ...shield, bt: toNumber(v) } })}
            />
          </div>
          <Field
            label="Текущие ПЗ щита"
            type="number"
            value={shield.current_hp}
            onChange={(v) => patchSheet({ shield: { ...shield, current_hp: toNumber(v) } })}
          />
        </div>
      </Section>

      <Section
        id="pf2e.hp"
        title="Пункты здоровья"
        defaultOpen
        summary={`${draft.hp_current}/${maxHp}`}
      >
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-2">
            <BigNumber
              label="Текущие"
              value={draft.hp_current}
              onChange={(value) => setNumberField('hp_current', value)}
            />
            <BigNumber label="Максимум" value={maxHp} readOnly hint="считается ниже" />
            <BigNumber
              label="Временные"
              value={hp.temporary}
              onChange={(value) => setHp('temporary', value)}
            />
          </div>

          <div className="grid grid-cols-2 gap-2">
            <Field
              label="При смерти"
              type="number"
              value={sheet.dying ?? 0}
              onChange={(v) => patchSheet({ dying: toNumber(v) })}
            />
            <Field
              label="Ранение"
              type="number"
              value={sheet.wounded ?? 0}
              onChange={(v) => patchSheet({ wounded: toNumber(v) })}
            />
          </div>

          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            <Field
              label="От народа"
              type="number"
              value={hp.ancestry}
              onChange={(v) => setHp('ancestry', v)}
            />
            <Field
              label="Класс за ур."
              type="number"
              value={hp.per_level}
              onChange={(v) => setHp('per_level', v)}
            />
            <Field label="Предмет" type="number" value={hp.item} onChange={(v) => setHp('item', v)} />
            <Field label="Прочее" type="number" value={hp.other} onChange={(v) => setHp('other', v)} />
            <Field
              label="Штраф"
              type="number"
              value={hp.penalty}
              onChange={(v) => setHp('penalty', v)}
            />
            <Field
              label="Скорость, фт."
              type="number"
              value={draft.speed}
              onChange={(v) => setNumberField('speed', v)}
            />
          </div>

          <p className="font-sans text-[11px] text-muted-foreground">
            {hp.ancestry} + ({hp.per_level} + {formatModifier(draft.con_mod)} ВЫН) × {draft.level} ур.
            = {maxHp}
          </p>

          <Field
            label="Типы перемещения и примечания"
            value={sheet.speed_notes ?? ''}
            onChange={(v) => patchSheet({ speed_notes: v })}
          />

          <Separator />
          <label className="block space-y-1">
            <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
              Устойчивость и невосприимчивость
            </span>
            <Textarea
              rows={2}
              value={sheet.resistances ?? ''}
              onChange={(event) => patchSheet({ resistances: event.target.value })}
            />
          </label>
        </div>
      </Section>

      <Section id="pf2e.saves" title="Испытания" defaultOpen>
        <div className="space-y-2">
          {SAVES.map((save) => (
            <StatRow
              key={save.key}
              label={save.label}
              abilityLabel={abilityLabel(save.ability)}
              abilityMod={abilityMod(save.ability)}
              level={draft.level}
              components={componentsFor(save.key)}
              onChange={(next) => setComponents(save.key, next)}
            />
          ))}
          <Field
            label="Примечания"
            value={sheet.saves_notes ?? ''}
            onChange={(v) => patchSheet({ saves_notes: v })}
          />
        </div>
      </Section>

      <Section id="pf2e.perception" title="Внимание и классовая СЛ" defaultOpen>
        <div className="space-y-2">
          <StatRow
            label="Восприятие"
            abilityLabel="МДР"
            abilityMod={draft.wis_mod}
            level={draft.level}
            components={componentsFor('perception')}
            onChange={(next) => setComponents('perception', next)}
          />
          <Field
            label="Чувства"
            value={sheet.senses ?? ''}
            onChange={(v) => patchSheet({ senses: v })}
          />
          <Separator />
          <StatRow
            label="Классовая СЛ"
            abilityLabel={abilityLabel(classDcAbility)}
            abilityMod={abilityMod(classDcAbility)}
            level={draft.level}
            base={10}
            components={componentsFor('class_dc')}
            onChange={(next) => setComponents('class_dc', next)}
          />
          <div className="flex flex-wrap items-center gap-1">
            <span className="mr-1 text-[10px] uppercase text-muted-foreground">Ключевая хар.:</span>
            {ABILITIES.map((ability) => (
              <button
                key={ability.key}
                type="button"
                onClick={() => patchSheet({ class_dc_ability: ability.key })}
                className={cn(
                  'rounded border px-2 py-0.5 text-xs',
                  ability.key === classDcAbility
                    ? 'border-secondary bg-secondary text-secondary-foreground'
                    : 'hover:bg-muted',
                )}
              >
                {ability.label}
              </button>
            ))}
          </div>
        </div>
      </Section>

      <Section id="pf2e.proficiencies" title="Владение бронёй и оружием">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1.5">
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Броня</p>
            {ARMOR_CATEGORIES.map((category) => (
              <LabeledRankRow
                key={category.key}
                label={category.label}
                rank={sheet.armor_proficiencies?.[category.key] ?? 'untrained'}
                onChange={(rank) => setRank('armor_proficiencies', category.key, rank)}
              />
            ))}
          </div>
          <div className="space-y-1.5">
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Оружие</p>
            {WEAPON_CATEGORIES.map((category) => (
              <LabeledRankRow
                key={category.key}
                label={category.label}
                rank={sheet.weapon_proficiencies?.[category.key] ?? 'untrained'}
                onChange={(rank) => setRank('weapon_proficiencies', category.key, rank)}
              />
            ))}
          </div>
        </div>
      </Section>

      <Section
        id="pf2e.conditions"
        title="Состояния"
        summary={
          activeConditions.length
            ? activeConditions
                .map(([key, value]) => {
                  const condition = CONDITIONS.find((entry) => entry.key === key)
                  return `${condition?.label ?? key}${value > 1 ? ` ${value}` : ''}`
                })
                .join(', ')
            : 'нет'
        }
      >
        <div className="flex flex-wrap gap-1.5">
          {CONDITIONS.map((condition) => {
            const value = conditions[condition.key] ?? 0
            return (
              <button
                key={condition.key}
                type="button"
                onClick={() => toggleCondition(condition.key, condition.valued)}
                title={condition.valued ? 'Нажимай, чтобы поднять значение' : undefined}
                className={cn(
                  'rounded-full border px-2.5 py-1 text-xs transition-colors',
                  value
                    ? 'border-primary bg-primary text-primary-foreground'
                    : 'border-dashed text-muted-foreground hover:bg-muted',
                )}
              >
                {condition.label}
                {condition.valued && value > 0 && ` ${value}`}
              </button>
            )
          })}
        </div>
      </Section>

      <StrikeBlock
        id="pf2e.melee"
        title="Удары в ближнем бою"
        ability="str"
        otherLabel="СИЛ к урону"
        items={sheet.melee_strikes ?? []}
        onChange={(melee_strikes) => patchSheet({ melee_strikes })}
      />
      <StrikeBlock
        id="pf2e.ranged"
        title="Дистанционные удары"
        ability="dex"
        otherLabel="Особое"
        items={sheet.ranged_strikes ?? []}
        onChange={(ranged_strikes) => patchSheet({ ranged_strikes })}
      />

      <Section id="pf2e.skills" title="Навыки" defaultOpen className="lg:col-span-2">
        <div className="grid gap-2 lg:grid-cols-2">
          {SKILLS.map((skill) => (
            <StatRow
              key={skill.key}
              label={skill.label}
              abilityLabel={abilityLabel(skill.ability)}
              abilityMod={abilityMod(skill.ability)}
              level={draft.level}
              components={componentsFor(skill.key)}
              onChange={(next) => setComponents(skill.key, next)}
              armorPenalty={skill.armorPenalty ? armorPenalty : 0}
              hint={abilityLabel(skill.ability)}
            />
          ))}
        </div>

        <div className="mt-4">
          <SectionTitle>Знание</SectionTitle>
          <div className="mt-2">
            <RepeatingList
              items={sheet.lore ?? []}
              onChange={(lore) => patchSheet({ lore })}
              blank={{ name: '', components: EMPTY_COMPONENTS }}
              addLabel="Добавить знание"
              renderRow={(entry, update) => (
                <div className="flex flex-wrap items-end gap-2">
                  <Field
                    label="Область знания"
                    value={entry.name}
                    onChange={(name) => update({ ...entry, name })}
                    className="min-w-40 flex-1"
                  />
                  <StatRow
                    label={entry.name || 'Знание'}
                    abilityLabel="ИНТ"
                    abilityMod={draft.int_mod}
                    level={draft.level}
                    components={entry.components}
                    onChange={(components) => update({ ...entry, components })}
                    className="min-w-56 flex-1"
                  />
                </div>
              )}
            />
          </div>
        </div>
      </Section>

      <Section id="pf2e.languages" title="Языки и заметки" className="lg:col-span-2">
        <div className="grid gap-3 lg:grid-cols-2">
          <label className="block space-y-1">
            <span className="text-[10px] uppercase tracking-wide text-muted-foreground">Языки</span>
            <Textarea
              rows={3}
              value={sheet.languages ?? ''}
              onChange={(event) => patchSheet({ languages: event.target.value })}
            />
          </label>
          <label className="block space-y-1">
            <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
              Заметки
            </span>
            <Textarea
              rows={3}
              value={sheet.notes ?? ''}
              onChange={(event) => patchSheet({ notes: event.target.value })}
            />
          </label>
        </div>
      </Section>
    </div>
  )
}
