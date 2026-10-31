export type GhostType = 'poltergeist' | 'sleepy' | 'shapeshifter' | 'twins'
export type Status = 'active' | 'kept' | 'cancelled' | 'cancel_requested'

export interface Ghost {
  id: string
  type: GhostType
  series_ids: string[]
  merchant_keys: string[]
  evidence: string[]
  yearly_cents: number
  currency: string
  next_date: string | null
  next_amount_cents: number | null
  display_name: string
  story: string | null
  epitaph: string | null
  explain: string | null
  cancel_email: { subject: string; body: string } | null
  fx_note: string | null
  waiting: boolean
  status: Status
  cancelled_at: string | null
  text_source: 'gemma' | 'template' | null
}

export interface Upcoming {
  merchant_key: string
  display_name: string
  date: string
  amount_cents: number
  currency: string
  ghost_type: GhostType | null
}

export interface Scan {
  today: string
  currency: string
  ghosts: Ghost[]
  total_ghost_yearly_cents: number
  total_subscriptions_yearly_cents: number
  saved_yearly_cents: number
  upcoming: Upcoming[]
  open_questions: number
  pending_enrich: number
}

export interface Series {
  id: string
  merchant_key: string
  interval: 'weekly' | 'monthly' | 'yearly'
  amounts: number[]
  currency: string
  next_date: string
  active: boolean
  essential: boolean
  category: string | null
  category_source: 'map' | 'user' | 'suggested' | null
  yearly_cents: number
}

export interface Question {
  id: string
  kind: 'subscription' | 'date_order' | 'fx'
  ref_id: string
  tag: string
  question: string
  why: string
  choice_a: string
  choice_b: string
  answer: 'a' | 'b' | null
}

export interface Mapping {
  date: number
  description: number
  amount: number | null
  debit: number | null
  credit: number | null
  currency: number | null
  original_amount: number | null
  original_currency: number | null
  date_order: 'ymd' | 'dmy' | 'mdy' | null
  default_currency: string
}

export interface Preview {
  upload_id: string
  signature: string
  headers: string[]
  rows: string[][]
  mapping: Mapping | null
  needs_user: boolean
  from_profile: boolean
  message: string | null
}

export interface LlmStatus {
  ok: boolean
  model: string
  error?: string
  fix?: string
}

export interface Me {
  auth_enabled: boolean
  logged_in: boolean
  name?: string
  agents_ready?: boolean
}

export interface CourierJob {
  request_id: string
  ghost_id: string
  state: 'waiting' | 'asking_phone' | 'sent' | 'denied' | 'timeout' | 'refused' | 'stopped' | 'error'
  message: string
  recipient_domain: string | null
}

/** Decoded claims only. The server never sends a raw token. */
export interface TokenView {
  sub: string
  act: Record<string, unknown> | null
  scope: string
  aud: string | string[]
  exp: number
  chain: string[]
  chain_names?: string[]
}

export interface AgentTokens {
  stopped: boolean
  penny: TokenView | null
  courier: TokenView | null
}

export interface AuditRow {
  request_id: string
  asked_by: string
  acted_by: string
  on_behalf_of: string
  ghost_id: string
  recipient_domain: string | null
  scope: string | null
  chain: string | null
  requested_at: string
  approved_at: string | null
  outcome: string | null
  outcome_at: string | null
  sent_at: string | null
  gmail_message_id: string | null
  note: string | null
}

export interface AskResult {
  text: string
  tools_used: { tool: string; args: Record<string, unknown> }[]
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init)
  if (!res.ok) {
    let detail = res.statusText
    try {
      detail = (await res.json()).detail ?? detail
    } catch {
      /* not JSON */
    }
    throw new Error(String(detail))
  }
  return res.json() as Promise<T>
}

const post = <T>(path: string, body?: unknown) =>
  call<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })

const enc = encodeURIComponent

export const api = {
  scan: () => call<Scan>('/api/scan'),
  series: () => call<Series[]>('/api/series'),
  questions: () => call<Question[]>('/api/questions'),
  config: () => call<Record<string, unknown>>('/api/config'),
  llmStatus: () => call<LlmStatus>('/api/llm/status'),
  me: () => call<Me>('/api/me'),
  cancelRequest: (ghostId: string, to_address: string) =>
    post<CourierJob>(`/api/ghosts/${enc(ghostId)}/cancel-request`, { to_address }),
  courierStatus: (requestId: string) => call<CourierJob>(`/api/courier/status/${enc(requestId)}`),
  agentTokens: () => call<AgentTokens>('/api/agents/tokens'),
  stopAgents: () => post<{ stopped: boolean }>('/api/agents/stop'),
  audit: () => call<AuditRow[]>('/api/audit'),
  enrich: () => post<{ enriched: number; seconds: number[] }>('/api/enrich'),
  answer: (id: string, choice: 'a' | 'b' | null) =>
    post(`/api/questions/${enc(id)}/answer`, { choice }),
  setStatus: (id: string, status: Status) => post(`/api/ghosts/${enc(id)}/status`, { status }),
  setCategory: (key: string, category: string) =>
    post(`/api/series/${enc(key)}/category`, { category }),
  ask: (question: string) => post<AskResult>('/api/ask', { question }),
  preview: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return call<Preview>('/api/import/preview', { method: 'POST', body: form })
  },
  commit: (upload_id: string, mapping: Mapping) =>
    post<{ imported: number; needs_user: boolean }>('/api/import/commit', { upload_id, mapping }),
}
