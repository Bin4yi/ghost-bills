import { useEffect, useState } from 'react'
import { api, type CourierJob, type Ghost } from '../api'

const FINAL = new Set(['sent', 'denied', 'timeout', 'refused', 'stopped', 'error'])

interface Props {
  ghost: Ghost
  onDone: () => void
}

/** You type the company's address. Courier sends only after you approve on your phone. */
export function SendWithGmail({ ghost, onDone }: Props) {
  const [open, setOpen] = useState(false)
  const [address, setAddress] = useState('')
  const [job, setJob] = useState<CourierJob | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  // A different ghost starts fresh: the address field is always empty.
  useEffect(() => {
    setOpen(false)
    setAddress('')
    setJob(null)
    setError(null)
  }, [ghost.id])

  // Follow the job until it ends.
  useEffect(() => {
    if (!job || FINAL.has(job.state)) {
      if (job) onDone()
      return
    }
    const t = setTimeout(async () => {
      try {
        setJob(await api.courierStatus(job.request_id))
      } catch (e) {
        setError(String(e))
      }
    }, 1500)
    return () => clearTimeout(t)
  }, [job, onDone])

  const ask = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      setJob(await api.cancelRequest(ghost.id, address.trim()))
    } catch (err) {
      setError(String(err).replace(/^Error: /, ''))
    } finally {
      setBusy(false)
    }
  }

  const inputId = `to-${ghost.id}`
  return (
    <div className="send-gmail">
      {!open && !job && (
        <>
          <button className="btn btn-primary" onClick={() => setOpen(true)}>
            Send with Gmail
          </button>
          <p className="muted small">
            Courier sends it from your Gmail only after you approve on your phone.
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
      {job && (
        <div className={`send-status state-${job.state}`} role="status" aria-live="polite">
          {job.state === 'asking_phone' && <span className="spinner" aria-hidden="true" />}
          <strong>{job.message}</strong>
          {job.recipient_domain && (
            <span className="muted small"> Email to {job.recipient_domain}</span>
          )}
          {FINAL.has(job.state) && job.state !== 'sent' && (
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
