import { useEffect, useState } from 'react'
import { api, type CourierJob, type Ghost } from '../api'

const FINAL = new Set(['sent', 'cancelled', 'expired', 'failed', 'refused', 'stopped', 'error'])

interface Props {
  ghost: Ghost
  onDone: () => void
  /** The result after coming back from the Auth0 approval, if it is for this ghost. */
  returned?: CourierJob | null
}

function clock(seconds: number): string {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

/** You type the company's address, then confirm by logging in again. Only then does Courier send. */
export function SendWithGmail({ ghost, onDone, returned = null }: Props) {
  const [open, setOpen] = useState(false)
  const [address, setAddress] = useState('')
  const [job, setJob] = useState<CourierJob | null>(null)
  const [left, setLeft] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  // A different ghost starts fresh (the address field is always empty), unless we just came
  // back from approving this one, or Penny prepared a send that waits for your approval.
  useEffect(() => {
    setOpen(false)
    setAddress('')
    setError(null)
    if (returned && returned.ghost_id === ghost.id) {
      setJob(returned)
      onDone()
      return
    }
    setJob(null)
    api
      .pendingSends()
      .then((list) => setJob(list.find((p) => p.ghost_id === ghost.id) ?? null))
      .catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ghost.id, returned])

  // Count down the 2 minutes the request is valid for.
  useEffect(() => {
    if (!job || job.state !== 'needs_approval') return
    setLeft(job.expires_in)
    const t = setInterval(() => setLeft((s) => Math.max(0, s - 1)), 1000)
    return () => clearInterval(t)
  }, [job])

  const ask = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const j = await api.cancelRequest(ghost.id, address.trim())
      setJob(j)
      if (FINAL.has(j.state)) onDone()
    } catch (err) {
      setError(String(err).replace(/^Error: /, ''))
    } finally {
      setBusy(false)
    }
  }

  const inputId = `to-${ghost.id}`
  const waiting = job?.state === 'needs_approval'
  const expired = waiting && left <= 0
  return (
    <div className="send-gmail">
      {!open && !job && (
        <>
          <button className="btn btn-primary" onClick={() => setOpen(true)}>
            Send with Gmail
          </button>
          <p className="muted small">
            Courier sends it from your Gmail only after you confirm it by logging in again.
          </p>
        </>
      )}
      {open && !job && (
        <form className="send-form" onSubmit={ask}>
          <label htmlFor={inputId}>The company's support email address</label>
          <input
            id={inputId}
            type="email"
            inputMode="email"
            autoComplete="off"
            spellCheck={false}
            required
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            placeholder="support@company.com"
          />
          <div className="row">
            <button className="btn btn-primary" disabled={busy || !address.trim()}>
              {busy ? 'Asking…' : 'Ask for approval'}
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => setOpen(false)}>
              Cancel
            </button>
          </div>
        </form>
      )}
      {job && waiting && !expired && job.step_up_url && (
        <div className="send-status state-waiting" role="status">
          {/* A full page navigation: Auth0 asks you to log in again, then sends you back here. */}
          <a className="btn btn-primary" href={job.step_up_url}>
            Confirm by logging in again
          </a>
          <p className="small">
            You'll go to Auth0 and log in once more to confirm this one email, then come straight
            back here. Email to <strong>{job.recipient_domain}</strong>. This request expires in{' '}
            <span className="mono">{clock(left)}</span>.
          </p>
        </div>
      )}
      {(expired || (job && FINAL.has(job.state))) && job && (
        <div
          className={`send-status state-${expired ? 'expired' : job.state}`}
          role="status"
          aria-live="polite"
        >
          <strong>{expired ? 'Not sent: approval expired' : job.message}</strong>
          {job.recipient_domain && (
            <span className="muted small"> Email to {job.recipient_domain}</span>
          )}
          {(expired || job.state !== 'sent') && (
            <button className="btn btn-secondary btn-small" onClick={() => setJob(null)}>
              Try again
            </button>
          )}
        </div>
      )}
      {error && (
        <p className="fx-note" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
