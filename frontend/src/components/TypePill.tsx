import type { GhostType } from '../api'
import { TYPES } from '../format'

/** A rubber stamp in the type's ink. The word is always shown, never colour alone. */
export function TypePill({ type }: { type: GhostType }) {
  return (
    <span className="stamp" style={{ '--type': `var(--${type})` } as React.CSSProperties}>
      {TYPES[type].word}
    </span>
  )
}
