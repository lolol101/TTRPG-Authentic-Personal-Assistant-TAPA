import { Section } from '@/components/Section'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import { Field, RepeatingList } from '@/rulesets/pf2e/components/SheetBits'
import { useSheet } from '@/rulesets/pf2e/sheetContext'
import { EMPTY_ACTION, EMPTY_FREE_ACTION } from '@/rulesets/pf2e/types'

function TextBlock({
  label,
  value,
  onChange,
  rows = 3,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  rows?: number
}) {
  return (
    <label className="block space-y-1">
      <span className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</span>
      <Textarea rows={rows} value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  )
}

export function BioTab() {
  const { sheet, patchSheet } = useSheet()

  const bio = sheet.bio ?? {}
  const personality = sheet.personality ?? {}
  const campaign = sheet.campaign ?? {}
  const actions = sheet.actions ?? []
  const freeActions = sheet.free_actions ?? []

  return (
    <div className="grid gap-3 lg:grid-cols-2">
      <Section
        id="pf2e.portrait"
        title="Портрет персонажа"
        defaultOpen
        className="lg:col-span-2"
        summary={[bio.age, bio.height, bio.weight].filter(Boolean).join(' · ') || 'не заполнено'}
      >
        <div className="space-y-3">
          <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-7">
            <Field
              label="Этнос"
              value={bio.ethnicity ?? ''}
              onChange={(v) => patchSheet({ bio: { ...bio, ethnicity: v } })}
            />
            <Field
              label="Национальность"
              value={bio.nationality ?? ''}
              onChange={(v) => patchSheet({ bio: { ...bio, nationality: v } })}
            />
            <Field
              label="Место рождения"
              value={bio.birthplace ?? ''}
              onChange={(v) => patchSheet({ bio: { ...bio, birthplace: v } })}
            />
            <Field
              label="Возраст"
              value={bio.age ?? ''}
              onChange={(v) => patchSheet({ bio: { ...bio, age: v } })}
            />
            <Field
              label="Пол и местоимения"
              value={bio.gender ?? ''}
              onChange={(v) => patchSheet({ bio: { ...bio, gender: v } })}
            />
            <Field
              label="Рост"
              value={bio.height ?? ''}
              onChange={(v) => patchSheet({ bio: { ...bio, height: v } })}
            />
            <Field
              label="Вес"
              value={bio.weight ?? ''}
              onChange={(v) => patchSheet({ bio: { ...bio, weight: v } })}
            />
          </div>
          <TextBlock
            label="Внешность"
            value={bio.appearance ?? ''}
            onChange={(v) => patchSheet({ bio: { ...bio, appearance: v } })}
          />
        </div>
      </Section>

      <Section id="pf2e.personality" title="Личность">
        <div className="space-y-3">
          <TextBlock
            label="Отношение"
            rows={2}
            value={personality.attitude ?? ''}
            onChange={(v) => patchSheet({ personality: { ...personality, attitude: v } })}
          />
          <TextBlock
            label="Верования"
            rows={2}
            value={personality.beliefs ?? ''}
            onChange={(v) => patchSheet({ personality: { ...personality, beliefs: v } })}
          />
          <div className="grid gap-3 sm:grid-cols-2">
            <TextBlock
              label="Любит"
              rows={2}
              value={personality.likes ?? ''}
              onChange={(v) => patchSheet({ personality: { ...personality, likes: v } })}
            />
            <TextBlock
              label="Не любит"
              rows={2}
              value={personality.dislikes ?? ''}
              onChange={(v) => patchSheet({ personality: { ...personality, dislikes: v } })}
            />
          </div>
          <TextBlock
            label="Меткие фразы"
            rows={2}
            value={personality.catchphrases ?? ''}
            onChange={(v) => patchSheet({ personality: { ...personality, catchphrases: v } })}
          />
        </div>
      </Section>

      <Section id="pf2e.campaign" title="Заметки для кампании">
        <div className="space-y-3">
          <TextBlock
            label="Заметки"
            rows={4}
            value={campaign.notes ?? ''}
            onChange={(v) => patchSheet({ campaign: { ...campaign, notes: v } })}
          />
          <TextBlock
            label="Союзники"
            rows={2}
            value={campaign.allies ?? ''}
            onChange={(v) => patchSheet({ campaign: { ...campaign, allies: v } })}
          />
          <TextBlock
            label="Враги"
            rows={2}
            value={campaign.enemies ?? ''}
            onChange={(v) => patchSheet({ campaign: { ...campaign, enemies: v } })}
          />
          <TextBlock
            label="Организации"
            rows={2}
            value={campaign.organizations ?? ''}
            onChange={(v) => patchSheet({ campaign: { ...campaign, organizations: v } })}
          />
        </div>
      </Section>

      <Section
        id="pf2e.actions"
        title="Действия и занятия"
        className="lg:col-span-2"
        summary={actions.length ? `${actions.length}` : 'пусто'}
      >
        <RepeatingList
          items={actions}
          onChange={(next) => patchSheet({ actions: next })}
          blank={EMPTY_ACTION}
          addLabel="Добавить действие"
          renderRow={(action, update) => (
            <div className="space-y-2">
              <div className="grid gap-2 sm:grid-cols-[2fr_1fr_2fr_1fr]">
                <Field
                  label="Название"
                  value={action.name}
                  onChange={(name) => update({ ...action, name })}
                />
                <Field
                  label="Действия"
                  value={action.actions}
                  onChange={(value) => update({ ...action, actions: value })}
                />
                <Field
                  label="Дескрипторы"
                  value={action.traits}
                  onChange={(traits) => update({ ...action, traits })}
                />
                <Field
                  label="Стр."
                  value={action.page}
                  onChange={(page) => update({ ...action, page })}
                />
              </div>
              <TextBlock
                label="Описание"
                rows={2}
                value={action.description}
                onChange={(description) => update({ ...action, description })}
              />
            </div>
          )}
        />
      </Section>

      <Section
        id="pf2e.free_actions"
        title="Свободные и ответные действия"
        className="lg:col-span-2"
        summary={freeActions.length ? `${freeActions.length}` : 'пусто'}
      >
        <RepeatingList
          items={freeActions}
          onChange={(next) => patchSheet({ free_actions: next })}
          blank={EMPTY_FREE_ACTION}
          addLabel="Добавить действие"
          renderRow={(action, update) => (
            <div className="space-y-2">
              <div className="grid gap-2 sm:grid-cols-[2fr_1fr_2fr_1fr]">
                <Field
                  label="Название"
                  value={action.name}
                  onChange={(name) => update({ ...action, name })}
                />
                <div className="flex items-end gap-1">
                  {(['free', 'reaction'] as const).map((kind) => (
                    <button
                      key={kind}
                      type="button"
                      onClick={() => update({ ...action, kind })}
                      className={cn(
                        'h-8 rounded border px-2 text-xs',
                        action.kind === kind
                          ? 'border-secondary bg-secondary text-secondary-foreground'
                          : 'hover:bg-muted',
                      )}
                    >
                      {kind === 'free' ? 'Свободное' : 'Ответное'}
                    </button>
                  ))}
                </div>
                <Field
                  label="Дескрипторы"
                  value={action.traits}
                  onChange={(traits) => update({ ...action, traits })}
                />
                <Field
                  label="Стр."
                  value={action.page}
                  onChange={(page) => update({ ...action, page })}
                />
              </div>
              <Field
                label="Условие"
                value={action.trigger}
                onChange={(trigger) => update({ ...action, trigger })}
              />
              <TextBlock
                label="Описание"
                rows={2}
                value={action.description}
                onChange={(description) => update({ ...action, description })}
              />
            </div>
          )}
        />
      </Section>
    </div>
  )
}
