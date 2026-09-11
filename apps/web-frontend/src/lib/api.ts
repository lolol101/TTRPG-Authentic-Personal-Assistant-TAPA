export interface UserResponse {
  id: number
  email: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
}

export interface AskSource {
  title: string
  url: string
  source_book: string
}

/** A sheet edit the assistant suggests. Applied only when the player says so. */
export interface ProposedChange {
  path: string
  value: unknown
  reason: string
  label: string
  before: unknown
}

export interface AskResponse {
  answer: string
  sources: AskSource[]
  proposed_changes: ProposedChange[]
  rejected_changes: string[]
}

/**
 * Ruleset-specific half of the sheet. Its shape is owned by the ruleset
 * module (see src/rulesets/<ruleset>/types.ts) — every game system has its
 * own sheet, so nothing generic may assume PF2e's fields.
 */
export type SheetData = Record<string, unknown>

export interface Character {
  id: number
  owner_id: number
  ruleset: string
  name: string
  ancestry: string
  background: string
  class_name: string
  level: number
  str_mod: number
  dex_mod: number
  con_mod: number
  int_mod: number
  wis_mod: number
  cha_mod: number
  hp_max: number
  hp_current: number
  ac: number
  speed: number
  sheet_data: SheetData
}

export type CharacterCreate = Partial<Omit<Character, 'id' | 'owner_id'>> & { name: string }
export type CharacterUpdate = Partial<Omit<Character, 'id' | 'owner_id'>>

export class ApiError extends Error {}

async function request<T>(path: string, token: string | null, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  })

  if (!response.ok) throw new ApiError(await parseErrorDetail(response))

  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

async function parseErrorDetail(response: Response): Promise<string> {
  try {
    const body = await response.json()
    if (typeof body.detail === 'string') return body.detail
  } catch {
    // fall through to the status line
  }
  return response.statusText
}

/**
 * Turns validated proposals into a PATCH body.
 *
 * The backend already decided each path is writable; this only merges them
 * into the character's current sheet so untouched fields survive the patch.
 */
export function buildPatchFromChanges(
  character: Character,
  changes: ProposedChange[],
): CharacterUpdate {
  const patch: Record<string, unknown> = {}
  let sheet: Record<string, unknown> | null = null

  for (const change of changes) {
    if (!change.path.startsWith('sheet_data.')) {
      patch[change.path] = change.value
      continue
    }
    sheet ??= structuredClone(character.sheet_data ?? {}) as Record<string, unknown>
    const parts = change.path.split('.').slice(1)
    let target = sheet
    for (const part of parts.slice(0, -1)) {
      const nested = target[part]
      if (typeof nested !== 'object' || nested === null) target[part] = {}
      target = target[part] as Record<string, unknown>
    }
    target[parts[parts.length - 1]] = change.value
  }

  if (sheet) patch.sheet_data = sheet
  return patch as CharacterUpdate
}

export interface AskStreamHandlers {
  onSources?: (sources: AskSource[]) => void
  onDelta?: (text: string) => void
  onDone?: (result: { proposed_changes: ProposedChange[]; rejected_changes: string[] }) => void
}

/**
 * Reads the answer as it is produced.
 *
 * The server frames this as server-sent events, but EventSource cannot send
 * an Authorization header or a POST body, so the stream is read off fetch by
 * hand. Frames are separated by a blank line and can be split across network
 * chunks, hence the carried-over buffer.
 */
async function streamAsk(
  token: string,
  question: string,
  characterId: number | undefined,
  handlers: AskStreamHandlers,
  ruleset?: string,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch('/llm/ask/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify({
      question,
      character_id: characterId ?? null,
      ruleset: ruleset ?? null,
    }),
    signal,
  })

  if (!response.ok || !response.body) {
    throw new ApiError(await parseErrorDetail(response))
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let split = buffer.indexOf('\n\n')
    while (split !== -1) {
      handleFrame(buffer.slice(0, split), handlers)
      buffer = buffer.slice(split + 2)
      split = buffer.indexOf('\n\n')
    }
  }

  if (buffer.trim()) handleFrame(buffer, handlers)
}

function handleFrame(frame: string, handlers: AskStreamHandlers): void {
  let name = ''
  const dataLines: string[] = []
  for (const line of frame.split('\n')) {
    if (line.startsWith('event:')) name = line.slice('event:'.length).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice('data:'.length).trimStart())
  }
  if (!name || !dataLines.length) return

  let data: unknown
  try {
    data = JSON.parse(dataLines.join('\n'))
  } catch {
    return
  }

  if (name === 'sources') handlers.onSources?.(data as AskSource[])
  else if (name === 'delta') handlers.onDelta?.((data as { text: string }).text)
  else if (name === 'done')
    handlers.onDone?.(
      data as { proposed_changes: ProposedChange[]; rejected_changes: string[] },
    )
  else if (name === 'error') throw new ApiError((data as { detail: string }).detail)
}

export const api = {
  register: (email: string, password: string) =>
    request<UserResponse>('/auth/register', null, {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),

  login: (email: string, password: string) =>
    request<TokenResponse>('/auth/login', null, {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),

  me: (token: string) => request<UserResponse>('/auth/me', token),

  ask: (token: string, question: string, characterId?: number) =>
    request<AskResponse>('/llm/ask', token, {
      method: 'POST',
      body: JSON.stringify({ question, character_id: characterId ?? null }),
    }),

  askStream: streamAsk,

  listCharacters: (token: string) => request<Character[]>('/characters', token),

  createCharacter: (token: string, payload: CharacterCreate) =>
    request<Character>('/characters', token, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updateCharacter: (token: string, id: number, payload: CharacterUpdate) =>
    request<Character>(`/characters/${id}`, token, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  deleteCharacter: (token: string, id: number) =>
    request<void>(`/characters/${id}`, token, { method: 'DELETE' }),
}
