import type { Ghost } from '../api'
import { day, money } from '../format'
import { artUrl, Mascot } from '../Mascot'

interface Props {
  ghosts: Ghost[]
  saved: number
  currency: string
  fresh: string | null
  onUndo: (id: string) => void
}

export function Graveyard({ ghosts, saved, currency, fresh, onUndo }: Props) {
  const strip = artUrl('graveyard_strip', 1024)
  return (
    <section
      className="graveyard"
      aria-labelledby="graveyard-title"
      style={strip ? { backgroundImage: `url(${strip})` } : undefined}
    >
      <div className="graveyard-head">
        <h2 id="graveyard-title">The Graveyard</h2>
        <p>
          Saved so far: <span className="mono saved">{money(saved, currency)}</span> per year
        </p>
      </div>
      {ghosts.length === 0 ? (
        <p className="muted graveyard-empty">
          Cancel a ghost and click “I cancelled it”. It will rest here.
        </p>
      ) : (
        <ul className="stones">
          {ghosts.map((g) => (
            <li key={g.id} className={`stone ${fresh === g.id ? 'fresh' : ''}`}>
              <Mascot name="gravestone" size={128} className="stone-art" />
              <div className="stone-text">
                <strong>{g.display_name}</strong>
                <span className="small">Laid to rest {day(g.cancelled_at)}</span>
                <em className="small">{g.epitaph}</em>
                <span className="mono saved small">+{money(g.yearly_cents, g.currency)}/yr</span>
              </div>
              <button className="btn btn-small" onClick={() => onUndo(g.id)}>
                Undo
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
