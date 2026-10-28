import type { Scan } from '../api'
import { money } from '../format'
import { Mascot } from '../Mascot'

interface Props {
  scan: Scan
  onSeance: () => void
}

export function BigNumber({ scan, onSeance }: Props) {
  const count = scan.ghosts.filter((g) => !g.waiting && g.status === 'active').length
  return (
    <section className="card big-number" aria-labelledby="big-number-title">
      <Mascot name={count ? 'penny_alarm' : 'penny_happy'} size={128} className="big-penny" />
      <div className="big-body">
        <h2 id="big-number-title" className="big-label">
          Your ghosts cost you
        </h2>
        <p className="big-amount">
          <span className="big-figure">
            <span aria-hidden="true">−</span>
            {money(scan.total_ghost_yearly_cents, scan.currency)}
          </span>
          <span className="per-year"> per year</span>
        </p>
        <p className="muted">
          All subscriptions:{' '}
          <span className="mono">{money(scan.total_subscriptions_yearly_cents, scan.currency)}</span>{' '}
          per year
        </p>
        <button className="btn btn-secondary" onClick={onSeance} disabled={count === 0}>
          🕯️ Start the séance
        </button>
      </div>
      {scan.saved_yearly_cents > 0 && (
        <div className="saved-box">
          <span className="label">Saved so far</span>
          <span className="mono saved">+{money(scan.saved_yearly_cents, scan.currency)}</span>
          <span className="small muted">per year</span>
        </div>
      )}
    </section>
  )
}
