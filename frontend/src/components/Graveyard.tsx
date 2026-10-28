import type { Ghost } from '../api'
import { day, money } from '../format'

interface Props {
  ghosts: Ghost[]
  saved: number
  currency: string
  fresh: string | null
  onUndo: (id: string) => void
}

export function Graveyard({ ghosts, saved, currency, fresh, onUndo }: Props) {
  return (
    <section className="card graveyard" aria-labelledby="graveyard-title">
      <div className="graveyard-head">
        <h2 id="graveyard-title" className="section-title">
          Laid to Rest
        </h2>
        <p className="saved-line">
          <span className="label">Saved so far</span>{' '}
          <span className="mono saved">{money(saved, currency)}</span> per year
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
              <div className="stone-face">
                <span className="stamp stamp-rest">Laid to rest</span>
                <strong className="stone-name">{g.display_name}</strong>
                <span className="small stone-date">Laid to rest {day(g.cancelled_at)}</span>
                <em className="stone-epitaph">{g.epitaph}</em>
                <span className="mono stone-saved">+{money(g.yearly_cents, g.currency)}/yr</span>
              </div>
              <button className="btn btn-secondary btn-small" onClick={() => onUndo(g.id)}>
                Undo
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
