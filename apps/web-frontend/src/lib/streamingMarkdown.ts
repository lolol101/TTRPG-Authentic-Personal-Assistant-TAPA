/**
 * Splits streamed assistant text into a part safe to compile as Markdown now
 * and a trailing part that must wait.
 *
 * A code fence is the one construct whose partial form reads as broken once
 * compiled (everything after an unclosed ``` would render as one giant code
 * block). Everything else in Markdown degrades gracefully mid-stream — an
 * unfinished **bold or a table missing its last row just prints as plain
 * text until the next chunk completes it — so only an open fence is held
 * back; the rest is returned as `stable` and compiled immediately.
 */
export function splitStreamingMarkdown(text: string): { stable: string; pending: string } {
  const fenceCount = text.match(/```/g)?.length ?? 0
  const hasOpenFence = fenceCount % 2 === 1
  if (!hasOpenFence) {
    return { stable: text, pending: '' }
  }

  const lastFenceStart = text.lastIndexOf('```')
  return { stable: text.slice(0, lastFenceStart), pending: text.slice(lastFenceStart) }
}
