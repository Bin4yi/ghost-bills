import { useEffect, useRef, useState } from 'react'
import type { Ghost } from '../api'
import { money } from '../format'
import { GHOST_ART, Mascot } from '../Mascot'
import { TypePill } from './TypePill'

interface Props {
  ghosts: Ghost[]
  total: number
  currency: string
  onClose: () => void
}

/** A different view of the same ghost data: no new model calls, no new numbers. */
export function Seance({ ghosts, total, currency, onClose }: Props) {
  const spirits = [...ghosts].sort((a, b) => b.yearly_cents - a.yearly_cents)
  const [i, setI] = useState(0)
  const nextRef = useRef<HTMLButtonElement>(null)
  const done = i >= spirits.length
  const g = spirits[i]

  useEffect(() => {
    nextRef.current?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [i, onClose])

  return (
    <div className="seance" role="dialog" aria-modal="true" aria-labelledby="seance-title">
      <div className="candles" aria-hidden="true">
        {[0, 1, 2].map((n) => (
          <span key={n} className={`candle c${n}`}>
            <span className="flame" />
          </span>
        ))}
      </div>
      <div className="seance-body">
        {done ? (
          <>
            <Mascot name="penny_seance" size={180} />
            <h2 id="seance-title">The séance is over.</h2>
            <p className="seance-line">
              I found {spirits.length} spirit{spirits.length === 1 ? '' : 's'}. Together they cost
              you <span className="mono">{money(total, currency)}</span> a year.
            </p>
          </>
        ) : (
          <>
            <p className="muted">
              Spirit {i + 1} of {spirits.length}
            </p>
            <Mascot name={GHOST_ART[g.type]} size={180} className="spirit" key={g.id} />
            <TypePill type={g.type} />
            <h2 id="seance-title">{g.display_name}</h2>
            <p className="seance-line">“{g.story}”</p>
            <p className="mono big-money">
              {money(g.yearly_cents, g.currency)}
              <span className="muted small"> per year</span>
            </p>
          </>
        )}
        <div className="row center">
          {!done && (
            <button ref={nextRef} className="btn btn-primary" onClick={() => setI(i + 1)}>
              Call the next spirit
            </button>
          )}
          <button ref={done ? nextRef : undefined} className="btn btn-secondary" onClick={onClose}>
            End séance
          </button>
        </div>
      </div>
    </div>
  )
}
