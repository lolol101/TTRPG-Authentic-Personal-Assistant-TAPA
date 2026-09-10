import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import { Field, RepeatingList, SectionTitle } from '@/rulesets/pf2e/components/SheetBits'
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

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <SectionTitle>Портрет персонажа</SectionTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-7">
            <Field label="Этнос" value={bio.ethnicity ?? ''} onChange={(v) => patchSheet({ bio: { ...bio, ethnicity: v } })} />
            <Field label="Национальность" value={bio.nationality ?? ''} onChange={(v) => patchSheet({ bio: { ...bio, nationality: v } })} />
            <Field label="Место рождения" value={bio.birthplace ?? ''} onChange={(v) => patchSheet({ bio: { ...bio, birthplace: v } })} />
            <Field label="Возраст" value={bio.age ?? ''} onChange={(v) => patchSheet({ bio: { ...bio, age: v } })} />
            <Field label="Пол и местоимения" value={bio.gender ?? ''} onChange={(v) => patchSheet({ bio: { ...bio, gender: v } })} />
            <Field label="Рост" value={bio.height ?? ''} onChange={(v) => patchSheet({ bio: { ...bio, height: v } })} />
            <Field label="Вес" value={bio.weight ?? ''} onChange={(v) => patchSheet({ bio: { ...bio, weight: v } })} />
          </div>
          <TextBlock
            label="Внешность"
            value={bio.appearance ?? ''}
            onChange={(v) => patchSheet({ bio: { ...bio, appearance: v } })}
          />
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <SectionTitle>Личность</SectionTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <TextBlock label="Отношение" value={personality.attitude ?? ''} onChange={(v) => patchSheet({ personality: { ...personality, attitude: v } })} rows={2} />
            <TextBlock label="Верования" value={personality.beliefs ?? ''} onChange={(v) => patchSheet({ personality: { ...personality, beliefs: v } })} rows={2} />
            <div className="grid gap-3 sm:grid-cols-2">
              <TextBlock label="Любит" value={personality.likes ?? ''} onChange={(v) => patchSheet({ personality: { ...personality, likes: v } })} rows={2} />
              <TextBlock label="Не любит" value={personality.dislikes ?? ''} onChange={(v) => patchSheet({ personality: { ...personality, dislikes: v } })} rows={2} />
            </div>
            <TextBlock label="Меткие фразы" value={personality.catchphrases ?? ''} onChange={(v) => patchSheet({ personality: { ...personality, catchphrases: v } })} rows={2} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <SectionTitle>Заметки для кампании</SectionTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <TextBlock label="Заметки" value={campaign.notes ?? ''} onChange={(v) => patchSheet({ campaign: { ...campaign, notes: v } })} rows={4} />
            <TextBlock label="Союзники" value={campaign.allies ?? ''} onChange={(v) => patchSheet({ campaign: { ...campaign, allies: v } })} rows={2} />
            <TextBlock label="Враги" value={campaign.enemies ?? ''} onChange={(v) => patchSheet({ campaign: { ...campaign, enemies: v } })} rows={2} />
            <TextBlock label="Организации" value={campaign.organizations ?? ''} onChange={(v) => patchSheet({ campaign: { ...campaign, organizations: v } })} rows={2} />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <SectionTitle>Действия и занятия</SectionTitle>
        </CardHeader>
        <CardContent>
          <RepeatingList
            items={sheet.actions ?? []}
            onChange={(actions) => patchSheet({ actions })}
            blank={EMPTY_ACTION}
            addLabel="Добавить действие"
            renderRow={(action, update) => (
              <div className="space-y-2">
                <div className="grid gap-2 sm:grid-cols-[2fr_1fr_2fr_1fr]">
                  <Field label="Название" value={action.name} onChange={(name) => update({ ...action, name })} />
                  <Field label="Действия" value={action.actions} onChange={(actions) => update({ ...action, actions })} />
                  <Field label="Дескрипторы" value={action.traits} onChange={(traits) => update({ ...action, traits })} />
                  <Field label="Стр." value={action.page} onChange={(page) => update({ ...action, page })} />
                </div>
                <TextBlock
                  label="Описание"
                  value={action.description}
                  onChange={(description) => update({ ...action, description })}
                  rows={2}
                />
              </div>
            )}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <SectionTitle>Свободные и ответные действия</SectionTitle>
        </CardHeader>
        <CardContent>
          <RepeatingList
            items={sheet.free_actions ?? []}
            onChange={(free_actions) => patchSheet({ free_actions })}
            blank={EMPTY_FREE_ACTION}
            addLabel="Добавить действие"
            renderRow={(action, update) => (
              <div className="space-y-2">
                <div className="grid gap-2 sm:grid-cols-[2fr_1fr_2fr_1fr]">
                  <Field label="Название" value={action.name} onChange={(name) => update({ ...action, name })} />
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
                  <Field label="Дескрипторы" value={action.traits} onChange={(traits) => update({ ...action, traits })} />
                  <Field label="Стр." value={action.page} onChange={(page) => update({ ...action, page })} />
                </div>
                <Field label="Условие" value={action.trigger} onChange={(trigger) => update({ ...action, trigger })} />
                <TextBlock
                  label="Описание"
                  value={action.description}
                  onChange={(description) => update({ ...action, description })}
                  rows={2}
                />
              </div>
            )}
          />
        </CardContent>
      </Card>
    </div>
  )
}
