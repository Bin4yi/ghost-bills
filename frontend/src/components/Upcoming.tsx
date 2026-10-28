import type { Series, Upcoming as Item } from '../api'
import { day, daysBetween, money } from '../format'
import { TypePill } from './TypePill'

interface Props {
  items: Item[]
  today: string
  series: Series[]
  onConfirmCategory: (key: string, category: string) => void
}

export function Upcoming({ items, today, series, onConfirmCategory }: Props) {
  const byKey = new Map(series.map((s) => [s.merchant_key, s]))
  return (
    <section className="card upcoming" aria-labelledby="upcoming-title">
      <h2 id="upcoming-title" className="section-title">Upcoming charges · next 30 days</h2>
      {items.length === 0 && <p className="muted">Nothing due in the next 30 days.</p>}
      <ol>
        {items.map((u) => {
          const s = byKey.get(u.merchant_key)
          return (
            <li key={u.merchant_key + u.date} className={u.ghost_type ? 'is-ghost' : ''}>
              <span className="up-date">
                <span className="mono">{day(u.date)}</span>
                <span className="muted small">in {daysBetween(today, u.date)} days</span>
              </span>
              <span className="up-name">
                {u.display_name}
                {u.ghost_type && <TypePill type={u.ghost_type} />}
                {s?.category && s.category_source === 'suggested' && (
                  <button
                    className="chip"
                    onClick={() => onConfirmCategory(s.merchant_key, s.category!)}
                    title="Gemma suggested this category. Confirm it so the rules can use it."
                  >
                    {s.category}? Confirm
                  </button>
                )}
                {s?.category && s.category_source !== 'suggested' && (
                  <span className="chip chip-static">{s.category}</span>
                )}
              </span>
              <span className="leader" aria-hidden="true" />
              <span className={`mono up-amount ${u.ghost_type ? 'lost' : ''}`}>
                {money(u.amount_cents, u.currency)}
              </span>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
