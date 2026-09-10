import { ChevronRight } from 'lucide-react'
import { useState } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'

const STORAGE_PREFIX = 'tapa.section.'

function readStored(id: string, fallback: boolean): boolean {
  try {
    const stored = localStorage.getItem(STORAGE_PREFIX + id)
    return stored === null ? fallback : stored === 'open'
  } catch {
    // Private windows and blocked site data throw on access; the section
    // still has to render, just without remembering anything.
    return fallback
  }
}

interface Props {
  /** Stable key the open/closed state is remembered under. */
  id: string
  title: string
  /** Shown in the header while collapsed, so a closed section still tells you something. */
  summary?: React.ReactNode
  defaultOpen?: boolean
  className?: string
  children: React.ReactNode
}

export function Section({ id, title, summary, defaultOpen = false, className, children }: Props) {
  const [open, setOpen] = useState(() => readStored(id, defaultOpen))

  function toggle() {
    const next = !open
    setOpen(next)
    try {
      localStorage.setItem(STORAGE_PREFIX + id, next ? 'open' : 'closed')
    } catch {
      // Not remembering the choice is survivable; failing to open is not.
    }
  }

  return (
    <Card className={cn('overflow-hidden py-0', className)}>
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        className="flex w-full items-center gap-2 px-4 py-2.5 text-left hover:bg-muted/50"
      >
        <ChevronRight
          className={cn('size-4 shrink-0 text-muted-foreground transition-transform', open && 'rotate-90')}
        />
        <span className="font-heading text-xl leading-none">{title}</span>
        {summary && !open && (
          <span className="ml-auto truncate font-sans text-xs text-muted-foreground">{summary}</span>
        )}
      </button>
      {open && <CardContent className="border-t pt-4">{children}</CardContent>}
    </Card>
  )
}
