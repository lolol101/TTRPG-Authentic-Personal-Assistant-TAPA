import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { splitStreamingMarkdown } from '@/lib/streamingMarkdown'

const components: Components = {
  p: ({ children }) => <p className="text-sm leading-relaxed [&:not(:last-child)]:mb-2">{children}</p>,
  h1: ({ children }) => <h1 className="mb-1.5 text-base font-semibold">{children}</h1>,
  h2: ({ children }) => <h2 className="mb-1.5 text-sm font-semibold">{children}</h2>,
  h3: ({ children }) => <h3 className="mb-1 text-sm font-semibold">{children}</h3>,
  ul: ({ children }) => <ul className="mb-2 list-disc space-y-0.5 pl-5 text-sm leading-relaxed">{children}</ul>,
  ol: ({ children }) => <ol className="mb-2 list-decimal space-y-0.5 pl-5 text-sm leading-relaxed">{children}</ol>,
  li: ({ children }) => <li>{children}</li>,
  a: ({ children, href }) => (
    <a href={href} target="_blank" rel="noreferrer" className="text-primary underline-offset-4 hover:underline">
      {children}
    </a>
  ),
  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
  blockquote: ({ children }) => (
    <blockquote className="mb-2 border-l-2 pl-3 text-muted-foreground">{children}</blockquote>
  ),
  hr: () => <hr className="my-2 border-border" />,
  code: ({ className, children }) => {
    // A fenced block's <code> sits inside <pre> and carries a language class;
    // an inline `code` span does not — that's the only reliable way to tell
    // them apart at this level of the tree.
    const isInline = !className
    return isInline ? (
      <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]">{children}</code>
    ) : (
      <code className="font-mono text-xs">{children}</code>
    )
  },
  pre: ({ children }) => (
    <pre className="mb-2 overflow-x-auto rounded border bg-muted p-2 leading-relaxed">{children}</pre>
  ),
  table: ({ children }) => (
    <div className="mb-2 overflow-x-auto">
      <table className="w-full border-collapse text-xs">{children}</table>
    </div>
  ),
  th: ({ children }) => <th className="border px-2 py-1 text-left font-medium">{children}</th>,
  td: ({ children }) => <td className="border px-2 py-1 align-top">{children}</td>,
}

interface Props {
  text: string
  /** Still arriving — holds back an unfinished code fence, shown raw meanwhile. */
  streaming?: boolean
}

const caret = (
  <span className="ml-0.5 inline-block h-4 w-[2px] animate-pulse bg-current align-text-bottom" />
)

/** Compiles an assistant reply's Markdown instead of showing the raw source. */
export function ChatMarkdown({ text, streaming = false }: Props) {
  const { stable, pending } = streaming ? splitStreamingMarkdown(text) : { stable: text, pending: '' }

  return (
    <div>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {stable}
      </ReactMarkdown>
      {pending && (
        <p className="whitespace-pre-wrap text-sm leading-relaxed">
          {pending}
          {streaming && caret}
        </p>
      )}
      {streaming && !pending && <p className="leading-none">{caret}</p>}
    </div>
  )
}
