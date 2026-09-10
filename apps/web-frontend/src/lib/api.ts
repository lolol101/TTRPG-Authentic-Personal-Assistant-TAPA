import type { ProficiencyRank } from '@/lib/pf2e'

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

export interface AskResponse {
  answer: string
  sources: AskSource[]
}

/** Free-form half of the sheet — see the Character model in web-backend. */
export interface SheetData {
  proficiencies?: Record<string, ProficiencyRank>
  hero_points?: number
  temp_hp?: number
  notes?: string
}

export interface Character {
  id: number
  owner_id: number
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

  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      // keep statusText
    }
    throw new ApiError(detail)
  }

  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
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

  ask: (question: string) =>
    request<AskResponse>('/llm/ask', null, {
      method: 'POST',
      body: JSON.stringify({ question }),
    }),

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
