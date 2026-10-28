import { useEffect, useState } from 'react'
import { api } from '../api'

const pct = (v: unknown) => `${Math.round(Number(v) * 100)}%`
const cents = (v: unknown) => `${(Number(v) / 100).toFixed(2)}`
const range = (v: unknown) => `${(v as number[])[0]}–${(v as number[])[1]} days`

export function HowWeDecide() {
  const [c, setC] = useState<Record<string, unknown> | null>(null)
  useEffect(() => {
    api.config().then(setC).catch(() => setC(null))
  }, [])
  if (!c) return null
  return (
    <details className="card how">
      <summary>How we decide (all rules are plain code)</summary>
      <ul>
        <li>
          A <strong>subscription</strong> needs {String(c.MIN_CHARGES)} charges (
          {String(c.MIN_CHARGES_YEARLY)} for yearly). Gaps: weekly {range(c.WEEKLY)}, monthly{' '}
          {range(c.MONTHLY)}, yearly {range(c.YEARLY)}. At least {pct(c.PATTERN_SHARE)} of gaps
          must fit, and prices must stay within ±{pct(c.AMOUNT_TOLERANCE)}.
        </li>
        <li>
          Between {pct(c.QUESTION_SHARE)} and {pct(c.PATTERN_SHARE)} of gaps fitting? Penny asks
          you instead of guessing.
        </li>
        <li>
          <strong>Poltergeist</strong>: newest price at least {pct(c.PRICE_UP_PCT)} and{' '}
          {cents(c.PRICE_UP_MIN_CENTS)} above the old price. Foreign charges are compared in their
          own currency. With no original amount, {pct(c.FX_PRICE_UP_PCT)} is needed, and smaller
          changes become a question.
        </li>
        <li>
          <strong>Sleepy Ghost</strong>: a yearly plan renewing within {String(c.RENEW_SOON_DAYS)}{' '}
          days.
        </li>
        <li>
          <strong>Shapeshifter</strong>: a first charge of {cents(c.TRIAL_MAX_CENTS)} or less (or
          under {pct(c.TRIAL_SHARE)} of the later price) in the last{' '}
          {String(c.TRIAL_WINDOW_DAYS)} days, then 2 full-price charges.
        </li>
        <li>
          <strong>Twin Ghosts</strong>: two active subscriptions in the same category. Only
          categories from the built-in list or confirmed by you count, never an AI guess.
        </li>
        <li>
          Rent, mortgage, loans, power, water and insurance are skipped as essentials.
          Subscriptions count as active if the last charge was within {String(c.ACTIVE_FACTOR)}×
          their interval.
        </li>
      </ul>
      <p className="muted small">
        AI explains, code finds, you decide. Gemma only writes the words, and a checker rejects any
        number, date or link that is not in the proof.
      </p>
    </details>
  )
}
