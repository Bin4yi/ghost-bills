import type { GhostType } from '../api'
import { TYPES } from '../format'

export function TypePill({ type }: { type: GhostType }) {
  return (
    <span className="pill" style={{ '--type': TYPES[type].color } as React.CSSProperties}>
      <span className="dot" aria-hidden="true" />
      {TYPES[type].word}
    </span>
  )
}
