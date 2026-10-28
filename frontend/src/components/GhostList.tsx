import type { Ghost } from '../api'
import { day, money } from '../format'
import { TypePill } from './TypePill'

interface Props {
  ghosts: Ghost[]
  selected: string | null
  onSelect: (id: string) => void
}

export function GhostList({ ghosts, selected, onSelect }: Props) {
  if (ghosts.length === 0) {
    return <p className="card muted empty">No ghosts here. Your statement looks calm.</p>
  }
  return (
    <ul className="ghost-list" aria-label="Ghosts, biggest money first">
      {ghosts.map((g) => (
        <li key={g.id}>
          <button
            className={`card ghost-row ${selected === g.id ? 'on' : ''} ${g.status === 'kept' ? 'kept' : ''}`}
            aria-current={selected === g.id}
            onClick={() => onSelect(g.id)}
          >
            <span className="ghost-row-top">
              <TypePill type={g.type} />
              {g.waiting && <span className="waiting">waiting for your answer</span>}
              {g.status === 'kept' && <span className="kept-tag">Kept</span>}
            </span>
            <span className="ghost-name">{g.display_name}</span>
            <span className="muted small line">{g.story ?? g.evidence[0]}</span>
            <span className="ghost-row-bottom">
              <span className="mono money">
                {money(g.yearly_cents, g.currency)}
                <span className="muted small"> /yr</span>
              </span>
              {g.next_date && <span className="muted small">Next: {day(g.next_date)}</span>}
            </span>
          </button>
        </li>
      ))}
    </ul>
  )
}
