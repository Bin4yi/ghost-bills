import type { GhostType } from './api'

const files = import.meta.glob('./assets/mascots/*.webp', {
  eager: true,
  import: 'default',
}) as Record<string, string>

export type MascotName =
  | 'penny_base'
  | 'penny_happy'
  | 'penny_alarm'
  | 'penny_thinking'
  | 'penny_question'
  | 'penny_seance'
  | 'ghost_sleepy'
  | 'ghost_poltergeist'
  | 'ghost_shapeshifter'
  | 'ghost_twins'
  | 'gravestone'
  | 'seance_candles'
  | 'logo_mark'
  | 'graveyard_strip'

export const GHOST_ART: Record<GhostType, MascotName> = {
  poltergeist: 'ghost_poltergeist',
  sleepy: 'ghost_sleepy',
  shapeshifter: 'ghost_shapeshifter',
  twins: 'ghost_twins',
}

export function artUrl(name: MascotName, width = 256): string | undefined {
  return (
    files[`./assets/mascots/${name}_${width}.webp`] ??
    Object.entries(files).find(([k]) => k.includes(`/${name}_`))?.[1]
  )
}

interface Props {
  name: MascotName
  size?: number
  alt?: string
  className?: string
}

/** A mascot picture, or a simple drawn stand-in if the art is missing. */
export function Mascot({ name, size = 96, alt = '', className = '' }: Props) {
  const src = artUrl(name, size > 128 ? 256 : 128)
  if (src) {
    return (
      <img src={src} width={size} height={size} alt={alt} className={`mascot ${className}`} />
    )
  }
  const isCat = name.startsWith('penny') || name === 'logo_mark'
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      role={alt ? 'img' : undefined}
      aria-label={alt || undefined}
      aria-hidden={alt ? undefined : true}
      className={`mascot ${className}`}
    >
      {isCat ? (
        <g>
          <path d="M14 26 L18 8 L28 20 Z M50 26 L46 8 L36 20 Z" fill="#2a2140" />
          <circle cx="32" cy="36" r="20" fill="#2a2140" />
          <circle cx="25" cy="34" r="4" fill="#F5D76E" />
          <circle cx="39" cy="34" r="4" fill="#F5D76E" />
        </g>
      ) : (
        <g>
          <path
            d="M14 56 V30 a18 18 0 0 1 36 0 V56 l-6-5 -6 5 -6-5 -6 5 -6-5 Z"
            fill="#EDE8F7"
          />
          <circle cx="26" cy="30" r="3" fill="#120E1C" />
          <circle cx="38" cy="30" r="3" fill="#120E1C" />
        </g>
      )}
    </svg>
  )
}
