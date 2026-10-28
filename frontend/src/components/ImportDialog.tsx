import { useEffect, useRef, useState } from 'react'
import { api, type Mapping, type Preview } from '../api'

interface Props {
  onClose: () => void
  onDone: (imported: number) => void
}

const FIELDS: { key: keyof Mapping; label: string; required?: boolean }[] = [
  { key: 'date', label: 'Date', required: true },
  { key: 'description', label: 'Description', required: true },
  { key: 'amount', label: 'Amount (one column)' },
  { key: 'debit', label: 'Money out (debit)' },
  { key: 'credit', label: 'Money in (credit)' },
  { key: 'original_amount', label: 'Original amount (foreign)' },
  { key: 'original_currency', label: 'Original currency' },
]

const EMPTY: Mapping = {
  date: 0,
  description: 1,
  amount: 2,
  debit: null,
  credit: null,
  currency: null,
  original_amount: null,
  original_currency: null,
  date_order: null,
  default_currency: 'USD',
}

export function ImportDialog({ onClose, onDone }: Props) {
  const ref = useRef<HTMLDialogElement>(null)
  const [preview, setPreview] = useState<Preview | null>(null)
  const [mapping, setMapping] = useState<Mapping>(EMPTY)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    ref.current?.showModal()
  }, [])

  const choose = async (file: File | undefined) => {
    if (!file) return
    setError(null)
    setBusy(true)
    try {
      const p = await api.preview(file)
      setPreview(p)
      setMapping(p.mapping ?? EMPTY)
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  const commit = async () => {
    if (!preview) return
    setBusy(true)
    try {
      const r = await api.commit(preview.upload_id, mapping)
      onDone(r.imported)
    } catch (e) {
      setError(String(e))
      setBusy(false)
    }
  }

  const set = (key: keyof Mapping, value: string) =>
    setMapping((m) => ({ ...m, [key]: value === '' ? null : Number(value) }))

  return (
    <dialog ref={ref} className="dialog" onClose={onClose} aria-labelledby="import-title">
      <h2 id="import-title">Import a bank statement (CSV)</h2>
      <p className="muted small">
        The file is read on this laptop only. No bank login, nothing is uploaded anywhere.
      </p>
      <label className="file">
        <span>Choose CSV file</span>
        <input type="file" accept=".csv,text/csv" onChange={(e) => choose(e.target.files?.[0])} />
      </label>
      {error && <p className="fx-note">{error}</p>}
      {preview && (
        <>
          {preview.message && <p className="fx-note">{preview.message}</p>}
          {preview.from_profile && (
            <p className="muted small">I remember this bank's columns from last time.</p>
          )}
          <div className="mapping">
            {FIELDS.map((f) => (
              <label key={f.key}>
                <span>{f.label}</span>
                <select
                  value={(mapping[f.key] as number | null) ?? ''}
                  onChange={(e) => set(f.key, e.target.value)}
                >
                  {!f.required && <option value="">— none —</option>}
                  {preview.headers.map((h, i) => (
                    <option key={i} value={i}>
                      {h}
                    </option>
                  ))}
                </select>
              </label>
            ))}
            <label>
              <span>Date order</span>
              <select
                value={mapping.date_order ?? ''}
                onChange={(e) =>
                  setMapping((m) => ({
                    ...m,
                    date_order: (e.target.value || null) as Mapping['date_order'],
                  }))
                }
              >
                <option value="">Not sure (Penny will ask)</option>
                <option value="dmy">Day first (31/12/2026)</option>
                <option value="mdy">Month first (12/31/2026)</option>
                <option value="ymd">Year first (2026-12-31)</option>
              </select>
            </label>
            <label>
              <span>Currency</span>
              <input
                value={mapping.default_currency}
                maxLength={3}
                onChange={(e) =>
                  setMapping((m) => ({ ...m, default_currency: e.target.value.toUpperCase() }))
                }
              />
            </label>
          </div>
          <div className="table-wrap">
            <table>
              <caption className="sr-only">First rows of the file</caption>
              <thead>
                <tr>
                  {preview.headers.map((h, i) => (
                    <th key={i}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((r, i) => (
                  <tr key={i}>
                    {r.map((c, j) => (
                      <td key={j}>{c}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      <div className="row end">
        <button className="btn btn-secondary" onClick={() => ref.current?.close()}>
          Cancel
        </button>
        <button className="btn btn-primary" disabled={!preview || busy} onClick={commit}>
          {busy ? 'Working…' : 'Import'}
        </button>
      </div>
    </dialog>
  )
}
