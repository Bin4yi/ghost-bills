import { useState } from 'react'
import { api, type AskResult } from '../api'
import { Mascot } from '../Mascot'

const SAMPLES = [
  'How much do I spend on music per year?',
  'Which ghost should I cancel first?',
  'When does CloudCrate renew?',
]

interface Message {
  q: string
  a?: AskResult
  error?: string
}

export function AskPenny({ llmOk }: { llmOk: boolean }) {
  const [messages, setMessages] = useState<Message[]>([])
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)

  const ask = async (q: string) => {
    if (!q.trim() || busy) return
    setText('')
    setBusy(true)
    setMessages((m) => [...m, { q }])
    try {
      const a = await api.ask(q)
      setMessages((m) => m.map((x, i) => (i === m.length - 1 ? { ...x, a } : x)))
    } catch (e) {
      setMessages((m) =>
        m.map((x, i) => (i === m.length - 1 ? { ...x, error: String(e) } : x)),
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card ask" aria-labelledby="ask-title">
      <div className="ask-head">
        <Mascot name={busy ? 'penny_thinking' : 'penny_base'} size={72} />
        <div>
          <h2 id="ask-title">Ask Penny</h2>
          <p className="muted small">
            Penny looks things up with read-only tools. Python does all the math.
          </p>
        </div>
      </div>
      {!llmOk && <p className="fx-note">Penny needs Gemma running in Ollama to answer.</p>}
      <div className="row wrap">
        {SAMPLES.map((s) => (
          <button key={s} className="chip" onClick={() => ask(s)} disabled={busy || !llmOk}>
            {s}
          </button>
        ))}
      </div>
      <div className="chat" aria-live="polite">
        {messages.map((m, i) => (
          <div key={i} className="msg">
            <p className="msg-q">{m.q}</p>
            {m.a && (
              <div className="msg-a">
                <p>{m.a.text}</p>
                {m.a.tools_used.length > 0 && (
                  <p className="tools">
                    {m.a.tools_used.map((t, j) => (
                      <span key={j} className="chip chip-static mono">
                        🔧 {t.tool}
                      </span>
                    ))}
                  </p>
                )}
              </div>
            )}
            {m.error && <p className="fx-note">{m.error}</p>}
            {!m.a && !m.error && <p className="muted thinking">Penny is thinking…</p>}
          </div>
        ))}
      </div>
      <form
        className="row ask-form"
        onSubmit={(e) => {
          e.preventDefault()
          ask(text)
        }}
      >
        <label htmlFor="ask-input" className="sr-only">
          Your question
        </label>
        <input
          id="ask-input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Ask about your subscriptions…"
          disabled={!llmOk}
        />
        <button className="btn btn-action" disabled={busy || !llmOk || !text.trim()}>
          Ask
        </button>
      </form>
    </section>
  )
}
