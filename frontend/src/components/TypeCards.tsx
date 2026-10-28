import type { Ghost, GhostType } from '../api'
import { money, TYPE_ORDER, TYPES } from '../format'
import { GHOST_ART, Mascot } from '../Mascot'

interface Props {
  ghosts: Ghost[]
  currency: string
  filter: GhostType | null
  onFilter: (t: GhostType | null) => void
}

export function TypeCards({ ghosts, currency, filter, onFilter }: Props) {
  return (
    <section className="type-cards" aria-label="Ghost types">
      {TYPE_ORDER.map((t) => {
        const mine = ghosts.filter((g) => g.type === t && g.status === 'active' && !g.waiting)
        const total = mine.reduce((sum, g) => sum + g.yearly_cents, 0)
        const on = filter === t
        return (
          <button
            key={t}
            className={`card type-card ${on ? 'on' : ''}`}
            style={{ '--type': TYPES[t].color } as React.CSSProperties}
            aria-pressed={on}
            onClick={() => onFilter(on ? null : t)}
          >
            <Mascot name={GHOST_ART[t]} size={56} />
            <span className="type-text">
              <span className="type-name">{TYPES[t].word}</span>
              <span className="muted small">{TYPES[t].meaning}</span>
              <span className="type-count">
                {mine.length} · <span className="mono">{money(total, currency)}</span>/yr
              </span>
            </span>
          </button>
        )
      })}
    </section>
  )
}
