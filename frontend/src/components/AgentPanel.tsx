import { useCallback, useEffect, useState } from 'react'
import { api, type AgentTokens, type AuditRow, type TokenView } from '../api'

function countdown(exp: number, now: number): string {
  const left = Math.round(exp - now / 1000)
  if (left <= 0) return 'expired'
  const m = Math.floor(left / 60)
  const s = String(left % 60).padStart(2, '0')
  return `expires in ${m}:${s}`
}

function TokenCard({ who, view, idle, now }: { who: string; view: TokenView | null; idle: string; now: number }) {
  return (
    <article className="token-card" aria-label={`${who}'s token`}>
      <h3>{who}</h3>
      {view ? (
        <dl className="claims">
          <dt>sub</dt>
          <dd className="mono">{view.sub}</dd>
          <dt>act</dt>
          <dd className="mono">{[...(view.chain_names ?? []), 'you'].join(' ← ')}</dd>
          <dt>scope</dt>
          <dd className="mono">{view.scope}</dd>
          <dt>aud</dt>
          <dd className="mono">{Array.isArray(view.aud) ? view.aud.join(', ') : view.aud}</dd>
          <dt>exp</dt>
          <dd className="mono">{countdown(view.exp, now)}</dd>
        </dl>
      ) : (
        <p className="muted mono small">{idle}</p>
      )}
    </article>
  )
}

function time(iso: string | null): string {
  if (!iso) return ''
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function steps(row: AuditRow, name: string): string[] {
  const asker = row.asked_by === 'you' ? 'You' : row.asked_by
  const out = [`${asker} asked Courier to send the ${name} email ${time(row.requested_at)}`]
  if (row.approved_at) out.push(`you approved on your phone ${time(row.approved_at)}`)
  switch (row.outcome) {
    case 'sent':
      out.push(`1 email sent to ${row.recipient_domain}`, 'Google token discarded')
      break
    case 'denied':
      out.push('you said no on your phone', 'nothing sent')
      break
    case 'timeout':
      out.push('no answer in time', 'nothing sent')
      break
    case 'refused':
      out.push(`Courier said no: ${row.note}`)
      break
    case 'stopped':
      out.push('agents stopped', 'nothing sent')
      break
    case 'error':
      out.push('something went wrong', 'nothing sent')
      break
    default:
      out.push('waiting for your phone…')
  }
  return out
}

interface Props {
  refreshKey: number
  ghostNames: Record<string, string>
}

/** "Who can do what right now", "Stop all agents" and "What Penny did". */
export function AgentPanel({ refreshKey, ghostNames }: Props) {
  const [tokens, setTokens] = useState<AgentTokens | null>(null)
  const [rows, setRows] = useState<AuditRow[]>([])
  const [now, setNow] = useState(Date.now())

  const load = useCallback(async () => {
    try {
      const [t, a] = await Promise.all([api.agentTokens(), api.audit()])
      setTokens(t)
      setRows(a)
    } catch {
      /* the API may be restarting */
    }
  }, [])

  useEffect(() => {
    load()
    const poll = setInterval(load, 3000)
    const tick = setInterval(() => setNow(Date.now()), 1000)
    return () => {
      clearInterval(poll)
      clearInterval(tick)
    }
  }, [load, refreshKey])

  const stop = async () => {
    await api.stopAgents()
    load()
  }

  return (
    <div className="split agents-split">
      <section className="card agents" aria-labelledby="agents-title">
        <h2 id="agents-title" className="section-title">
          Who can do what right now
        </h2>
        {tokens?.stopped && (
          <p className="stopped-banner" role="status">
            Agents stopped. Their tokens are gone. Log out and in again to start them.
          </p>
        )}
        <div className="token-cards">
          <TokenCard who="Penny" view={tokens?.penny ?? null} idle="no token yet" now={now} />
          <TokenCard who="Courier" view={tokens?.courier ?? null} idle="no token" now={now} />
        </div>
        <p className="muted small">
          Decoded claims only. Raw tokens stay in the server's memory and are never shown.
        </p>
        <button className="btn btn-secondary stop-btn" onClick={stop} disabled={tokens?.stopped}>
          {tokens?.stopped ? 'Agents stopped' : 'Stop all agents'}
        </button>
      </section>

      <section className="card timeline" aria-labelledby="timeline-title">
        <h2 id="timeline-title" className="section-title">
          What Penny did
        </h2>
        {rows.length === 0 ? (
          <p className="muted">Nothing yet. Penny can only ask; you approve every email.</p>
        ) : (
          <ol className="audit-list">
            {rows.map((r) => (
              <li key={r.request_id} className={`audit-row outcome-${r.outcome ?? 'waiting'}`}>
                <p>{steps(r, ghostNames[r.ghost_id] ?? r.ghost_id).join(' → ')}</p>
                {r.chain && <p className="muted small mono">{r.chain}</p>}
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  )
}
