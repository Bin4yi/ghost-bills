import type { GhostType } from './api'

/** 1299 -> "$12.99". Always shows the currency. Integer cents in, text out. */
export function money(cents: number, currency = 'USD'): string {
  const sign = cents < 0 ? '-' : ''
  const abs = Math.abs(cents)
  const whole = Math.floor(abs / 100).toLocaleString('en-US')
  const part = String(abs % 100).padStart(2, '0')
  const symbol = ({ USD: '$', EUR: '€', GBP: '£' } as Record<string, string>)[currency]
  return symbol ? `${sign}${symbol}${whole}.${part}` : `${sign}${currency} ${whole}.${part}`
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** "2026-11-05" -> "5 Nov 2026" (no time zone surprises). */
export function day(iso: string | null | undefined): string {
  if (!iso) return ''
  const [y, m, d] = iso.split('-').map(Number)
  return `${d} ${MONTHS[m - 1]} ${y}`
}

export function daysBetween(fromIso: string, toIso: string): number {
  const a = Date.UTC(...(fromIso.split('-').map(Number) as [number, number, number]))
  const b = Date.UTC(...(toIso.split('-').map(Number) as [number, number, number]))
  return Math.round((b - a) / 86_400_000)
}

export const TYPES: Record<GhostType, { word: string; color: string; meaning: string }> = {
  poltergeist: { word: 'Poltergeist', color: '#FF7A6B', meaning: 'Price went up' },
  sleepy: { word: 'Sleepy Ghost', color: '#7FE3C4', meaning: 'Yearly plan wakes soon' },
  shapeshifter: { word: 'Shapeshifter', color: '#F2B24A', meaning: 'Free trial turned paid' },
  twins: { word: 'Twin Ghosts', color: '#C4B3F7', meaning: 'Two doing one job' },
}

export const TYPE_ORDER: GhostType[] = ['poltergeist', 'sleepy', 'shapeshifter', 'twins']
