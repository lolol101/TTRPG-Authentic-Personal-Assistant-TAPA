import { readFileSync } from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'

/**
 * Guards the dev proxy against drifting behind the API client.
 *
 * A backend prefix missing from vite.config.ts fails in a way that looks
 * like a broken backend rather than a broken config: Vite answers GET with
 * its own index.html and POST with a bare 404, so the page reports
 * "Not Found" for an endpoint that is running fine one port over. That is
 * exactly how /chats shipped, and no test noticed — the backend was tested
 * on its own port, and the browser never reached it.
 */

const root = path.resolve(import.meta.dirname, '../..')

function proxiedPrefixes(): string[] {
  const config = readFileSync(path.join(root, 'vite.config.ts'), 'utf8')
  const block = config.slice(config.indexOf('proxy: {'))
  return [...block.matchAll(/'(\/[a-z-]+)':/g)].map((match) => match[1])
}

/** Every absolute path the API client sends a request to. */
function requestedPaths(): string[] {
  const source = readFileSync(path.join(root, 'src/lib/api.ts'), 'utf8')
  // Covers both request('/path', …) and fetch('/path', …), template
  // literals included — `/chats/${id}/messages` counts as /chats.
  return [...source.matchAll(/(?:request<[^>]*>|fetch)\(\s*[`'](\/[^`'$]*)/g)].map(
    (match) => match[1],
  )
}

describe('dev proxy', () => {
  it('forwards every path the API client calls', () => {
    const prefixes = proxiedPrefixes()
    const missing = requestedPaths().filter(
      (requested) => !prefixes.some((prefix) => requested.startsWith(prefix)),
    )

    expect(missing).toEqual([])
  })

  it('finds the paths it is supposed to be checking', () => {
    // Without this, a broken regex would leave the test above passing on an
    // empty list and guarding nothing at all.
    const paths = requestedPaths()

    expect(paths.length).toBeGreaterThan(5)
    expect(paths).toContain('/chats')
  })

  it('reads a proxy table rather than an empty match', () => {
    expect(proxiedPrefixes()).toContain('/auth')
  })
})
