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
      <div>
        <h2 id="big-number-title" className="big-label">
          Your ghosts cost you
        </h2>
        <p className="big-amount mono">
          {money(scan.total_ghost_yearly_cents, scan.currency)}
          <span className="per-year"> per year</span>
        </p>
        <p className="muted">
          All subscriptions:{' '}
          <span className="mono">{money(scan.total_subscriptions_yearly_cents, scan.currency)}</span>{' '}
          per year
          {scan.saved_yearly_cents > 0 && (
            <>
              {' · '}
              <span className="saved">
                Saved so far:{' '}
                <span className="mono">{money(scan.saved_yearly_cents, scan.currency)}</span> per
                year
              </span>
            </>
          )}
        </p>
        <button className="btn btn-ghost" onClick={onSeance} disabled={count === 0}>
          🕯️ Start the séance
        </button>
      </div>
    </section>
  )
}
