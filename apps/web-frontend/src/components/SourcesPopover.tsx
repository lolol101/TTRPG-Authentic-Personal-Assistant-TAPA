import { BookOpen, ChevronDown } from 'lucide-react'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import type { AskSource } from '@/lib/api'

interface Props {
  sources: AskSource[]
}

/**
 * The citations behind an answer, folded away until asked for.
 *
 * Every answer carries its sources, and printed in full they crowded out the
 * answer itself — a long chat became a wall of links. The count stays visible
 * so an answer still says how much it rests on; the list opens over the chat
 * instead of pushing it around.
 */
export function SourcesPopover({ sources }: Props) {
  return (
    <div className="border-t pt-2">
      <Popover>
        <PopoverTrigger className="group inline-flex items-center gap-1 rounded text-[10px] font-medium uppercase tracking-wide text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50">
          <BookOpen className="size-3" />
          Источники · {sources.length}
          <ChevronDown className="size-3 transition-transform group-aria-expanded:rotate-180" />
        </PopoverTrigger>
        <PopoverContent>
          <p className="mb-2 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            Источники ответа
          </p>
          <ul className="space-y-1.5 text-xs">
            {sources.map((source) => (
              <li key={source.url}>
                <a
                  href={source.url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-primary underline-offset-4 hover:underline"
                >
                  {source.title}
                </a>
                {source.source_book && (
                  <span className="block text-muted-foreground">{source.source_book}</span>
                )}
              </li>
            ))}
          </ul>
        </PopoverContent>
      </Popover>
    </div>
  )
}
