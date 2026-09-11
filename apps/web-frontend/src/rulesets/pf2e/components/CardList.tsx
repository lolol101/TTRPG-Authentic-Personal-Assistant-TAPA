import { ChevronRight, Plus, X } from 'lucide-react'
import { useState } from 'react'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import {
  blankCard,
  cardSummary,
  type Card,
  type CardField,
  type CardSchema,
} from '@/rulesets/pf2e/cards'

function FieldInput({
  field,
  value,
  onChange,
}: {
  field: CardField
  value: Card[string]
  onChange: (value: Card[string]) => void
}) {
  if (field.kind === 'checkbox') {
    return (
      <label className="flex h-8 items-center gap-2 text-xs">
        <input
          type="checkbox"
          checked={Boolean(value)}
          onChange={(event) => onChange(event.target.checked)}
        />
        {field.label}
      </label>
    )
  }

  const label = (
    <span className="text-[10px] uppercase tracking-wide text-muted-foreground">{field.label}</span>
  )

  if (field.kind === 'textarea') {
    return (
      <label className="block space-y-1">
        {label}
        <Textarea
          rows={3}
          value={String(value ?? '')}
          onChange={(event) => onChange(event.target.value)}
        />
      </label>
    )
  }

  if (field.kind === 'select') {
    return (
      <label className="block space-y-1">
        {label}
        <select
          value={String(value ?? '')}
          onChange={(event) => onChange(event.target.value)}
          className="h-8 w-full rounded-md border border-input bg-background px-2 text-sm"
        >
          <option value="">—</option>
          {field.options?.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </label>
    )
  }

  return (
    <label className="block space-y-1">
      {label}
      <Input
        type={field.kind === 'number' ? 'number' : 'text'}
        value={String(value ?? '')}
        onChange={(event) =>
          onChange(
            field.kind === 'number'
              ? Number.parseInt(event.target.value, 10) || 0
              : event.target.value,
          )
        }
        className="h-8"
      />
    </label>
  )
}

function CardRow({
  schema,
  card,
  onChange,
  onDelete,
  startOpen,
}: {
  schema: CardSchema
  card: Card
  onChange: (card: Card) => void
  onDelete: () => void
  startOpen: boolean
}) {
  const [open, setOpen] = useState(startOpen)
  const name = String(card.name ?? '')
  const summary = cardSummary(schema, card)

  return (
    <div className="rounded-md border bg-card/60">
      <div className="flex items-center gap-2 px-2 py-1.5">
        <button
          type="button"
          onClick={() => setOpen(!open)}
          aria-expanded={open}
          className="flex min-w-0 flex-1 items-center gap-2 text-left"
        >
          <ChevronRight
            className={cn(
              'size-3.5 shrink-0 text-muted-foreground transition-transform',
              open && 'rotate-90',
            )}
          />
          <span className={cn('truncate text-sm', !name && 'text-muted-foreground')}>
            {name || 'Без названия'}
          </span>
          {summary && !open && (
            <span className="truncate font-sans text-[11px] text-muted-foreground">{summary}</span>
          )}
        </button>
        <button
          type="button"
          title="Удалить"
          onClick={onDelete}
          className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-destructive"
        >
          <X className="size-3.5" />
        </button>
      </div>

      {open && (
        <div className="grid gap-2 border-t bg-background/40 p-2.5 sm:grid-cols-2 lg:grid-cols-4">
          {schema.fields.map((field) => (
            <div key={field.key} className={cn(field.wide && 'sm:col-span-2 lg:col-span-4')}>
              <FieldInput
                field={field}
                value={card[field.key]}
                onChange={(value) => onChange({ ...card, [field.key]: value })}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

interface Props {
  schema: CardSchema
  cards: Card[]
  onChange: (cards: Card[]) => void
  /** Stamped onto every card this list creates, e.g. the feat category. */
  defaults?: Card
  emptyHint?: string
}

export function CardList({ schema, cards, onChange, defaults, emptyHint }: Props) {
  // A card added just now opens itself: you added it in order to fill it in.
  const [openIndex, setOpenIndex] = useState<number | null>(null)

  function add() {
    onChange([...cards, { ...blankCard(schema), ...defaults }])
    setOpenIndex(cards.length)
  }

  return (
    <div className="space-y-1.5">
      {cards.length === 0 && emptyHint && (
        <p className="text-xs text-muted-foreground">{emptyHint}</p>
      )}

      {cards.map((card, index) => (
        <CardRow
          key={index}
          schema={schema}
          card={card}
          startOpen={index === openIndex}
          onChange={(next) => onChange(cards.map((entry, i) => (i === index ? next : entry)))}
          onDelete={() => {
            onChange(cards.filter((_, i) => i !== index))
            setOpenIndex(null)
          }}
        />
      ))}

      <button
        type="button"
        onClick={add}
        className="flex items-center gap-1.5 rounded-md border border-dashed px-3 py-1.5 text-xs text-muted-foreground hover:bg-muted"
      >
        <Plus className="size-3.5" />
        {schema.addLabel}
      </button>
    </div>
  )
}
