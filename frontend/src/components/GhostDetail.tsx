import { useState } from 'react'
import type { Ghost, Status } from '../api'
import { money } from '../format'
import { GHOST_ART, Mascot } from '../Mascot'
import { TypePill } from './TypePill'

// Amounts and dates in a proof line, so they can be set in the ledger's typewriter face.
const FIGURES =
  /([$€£]?-?\d[\d,]*(?:\.\d+)?(?:\s(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s\d{4})?|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s\d{4})/

function Figures({ text }: { text: string }) {
  return (
    <>
      {text.split(FIGURES).map((part, i) =>
        i % 2 ? (
          <span key={i} className="mono">
            {part}
          </span>
        ) : (
          part
        ),
      )}
    </>
  )
}

interface Props {
  ghost: Ghost | null
  onStatus: (id: string, status: Status) => void
}

export function GhostDetail({ ghost, onStatus }: Props) {
  const [copied, setCopied] = useState(false)
  if (!ghost) {
    return <aside className="card detail muted">Pick a ghost to see the proof.</aside>
  }
  const email = ghost.cancel_email
  const copy = async () => {
    if (!email) return
    await navigator.clipboard.writeText(`Subject: ${email.subject}\n\n${email.body}`)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <aside id="detail" className="card detail" aria-labelledby="detail-title">
      <div className="detail-head">
        <Mascot name={GHOST_ART[ghost.type]} size={112} />
        <div>
          <TypePill type={ghost.type} />
          <h2 id="detail-title" className={ghost.status === 'kept' ? 'struck' : ''}>
            {ghost.display_name}
          </h2>
          <p className="mono big-money">
            {money(ghost.yearly_cents, ghost.currency)}
            <span className="muted small"> per year</span>
          </p>
          {ghost.fx_note && (
            <p className="fx-note">
              ⚠️ Price changed, but maybe it is only the exchange rate. The statement does not
              show the original price.
            </p>
          )}
          {ghost.waiting && (
            <p className="waiting">Waiting for your answer above. Not counted yet.</p>
          )}
        </div>
      </div>

      {ghost.story && <p className="story">“{ghost.story}”</p>}

      <h3>Proof (found by code, not AI)</h3>
      <ul className="proof">
        {ghost.evidence.map((e) => (
          <li key={e}>
            <Figures text={e} />
          </li>
        ))}
      </ul>

      <h3>
        Why it matters{' '}
        <span className={`badge ${ghost.text_source === 'gemma' ? 'badge-gemma' : ''}`}>
          {ghost.text_source === 'gemma' ? 'Gemma · local' : 'template text'}
        </span>
      </h3>
      <p>{ghost.explain}</p>

      {email && (
        <>
          <h3>Cancel email</h3>
          <div className="email">
            <p>
              <strong>Subject:</strong> {email.subject}
            </p>
            <pre>{email.body}</pre>
          </div>
          <p className="muted small">
            Find the cancel option in your account settings, or send this email to the company's
            support address. Ghost Bills never sends anything for you.
          </p>
          <div className="row">
            <button className="btn btn-secondary" onClick={copy}>
              {copied ? 'Copied ✓' : 'Copy email'}
            </button>
          </div>
        </>
      )}

      <div className="row decide">
        <button
          className="btn btn-secondary"
          onClick={() => onStatus(ghost.id, ghost.status === 'kept' ? 'active' : 'kept')}
        >
          {ghost.status === 'kept' ? 'Undo keep' : 'Keep it'}
        </button>
        <button className="btn btn-primary" onClick={() => onStatus(ghost.id, 'cancelled')}>
          I cancelled it
        </button>
      </div>
    </aside>
  )
}
