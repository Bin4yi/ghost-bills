import { useCallback, useEffect, useMemo, useState } from 'react'
import { api, type GhostType, type LlmStatus, type Me, type Question, type Scan, type Series, type Status } from './api'
import { AgentPanel } from './components/AgentPanel'
import { AskPenny } from './components/AskPenny'
import { BigNumber } from './components/BigNumber'
import { GhostDetail } from './components/GhostDetail'
import { GhostList } from './components/GhostList'
import { Graveyard } from './components/Graveyard'
import { Header } from './components/Header'
import { HowWeDecide } from './components/HowWeDecide'
import { ImportDialog } from './components/ImportDialog'
import { QuestionCards } from './components/QuestionCards'
import { Seance } from './components/Seance'
import { TypeCards } from './components/TypeCards'
import { Upcoming } from './components/Upcoming'
import { Mascot } from './Mascot'

export default function App() {
  const [scan, setScan] = useState<Scan | null>(null)
  const [series, setSeries] = useState<Series[]>([])
  const [questions, setQuestions] = useState<Question[]>([])
  const [llm, setLlm] = useState<LlmStatus | null>(null)
  const [me, setMe] = useState<Me | null>(null)
  const [agentRefresh, setAgentRefresh] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<GhostType | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [importing, setImporting] = useState(false)
  const [seance, setSeance] = useState(false)
  const [writing, setWriting] = useState(false)
  const [fresh, setFresh] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const [s, sr, q] = await Promise.all([api.scan(), api.series(), api.questions()])
      setScan(s)
      setSeries(sr)
      setQuestions(q)
      setError(null)
      return s
    } catch (e) {
      setError(`Cannot reach the Ghost Bills API. Start it with: make api (${e})`)
      return null
    }
  }, [])

  /** Gemma writes the words once per ghost; results are cached by the backend. */
  const enrich = useCallback(
    async (s: Scan | null, status: LlmStatus | null) => {
      if (!s || !status?.ok || s.pending_enrich === 0) return
      setWriting(true)
      try {
        await api.enrich()
        await refresh()
      } finally {
        setWriting(false)
      }
    },
    [refresh],
  )

  useEffect(() => {
    ;(async () => {
      const [s, status] = await Promise.all([
        refresh(),
        api.llmStatus().catch(() => null),
      ])
      setLlm(status)
      enrich(s, status)
      api.me().then(setMe).catch(() => setMe(null))
    })()
  }, [refresh, enrich])

  const live = useMemo(
    () => (scan?.ghosts ?? []).filter((g) => g.status !== 'cancelled'),
    [scan],
  )
  const shown = filter ? live.filter((g) => g.type === filter) : live
  const current = live.find((g) => g.id === selected) ?? shown[0] ?? null
  const buried = (scan?.ghosts ?? []).filter((g) => g.status === 'cancelled')
  const counted = live.filter((g) => !g.waiting && g.status === 'active')

  // Sending needs a login and both agent clients; logged out, the app stays fully local.
  const agentsOn = !!(me?.auth_enabled && me.logged_in && me.agents_ready)
  const onSendDone = useCallback(() => {
    setAgentRefresh((n) => n + 1)
    refresh()
  }, [refresh])

  const setStatus = async (id: string, status: Status) => {
    await api.setStatus(id, status)
    if (status === 'cancelled') {
      setFresh(id)
      setSelected(null)
    }
    await refresh()
  }

  const answer = async (id: string, choice: 'a' | 'b' | null) => {
    await api.answer(id, choice)
    const s = await refresh()
    enrich(s, llm)
  }

  const confirmCategory = async (key: string, category: string) => {
    await api.setCategory(key, category)
    const s = await refresh()
    enrich(s, llm)
  }

  return (
    <div className="page">
      <a className="skip" href="#ghosts">
        Skip to ghosts
      </a>
      <Header me={me} onImport={() => setImporting(true)} />

      {llm && !llm.ok && (
        <div className="card notice" role="status">
          <Mascot name="penny_question" size={56} />
          <div>
            <strong>Gemma is not running, so Penny uses simple template text.</strong>
            <p className="small muted">
              Finding ghosts and all the money math still work. To get Gemma's words, start
              Ollama and run: <code>{llm.fix ?? 'ollama pull gemma3:4b'}</code>
            </p>
          </div>
        </div>
      )}
      {error && (
        <div className="card notice" role="alert">
          {error}
        </div>
      )}
      {writing && (
        <p className="card notice" role="status">
          <span className="spinner" aria-hidden="true" /> Gemma is writing the ghost stories on
          your laptop…
        </p>
      )}

      {scan && (
        <main>
          <BigNumber scan={scan} onSeance={() => setSeance(true)} />
          <TypeCards ghosts={live} currency={scan.currency} filter={filter} onFilter={setFilter} />
          <QuestionCards questions={questions} onAnswer={answer} />

          <div className="split" id="ghosts">
            <GhostList
              ghosts={shown}
              selected={current?.id ?? null}
              onSelect={(id) => {
                setSelected(id)
                // On phones the details sit below the list.
                if (window.innerWidth < 860) {
                  requestAnimationFrame(() =>
                    document.getElementById('detail')?.scrollIntoView({ block: 'start' }),
                  )
                }
              }}
            />
            <GhostDetail
              ghost={current}
              onStatus={setStatus}
              canSend={agentsOn}
              onSendDone={onSendDone}
            />
          </div>

          <div className="split">
            <Upcoming
              items={scan.upcoming}
              today={scan.today}
              series={series}
              onConfirmCategory={confirmCategory}
            />
            <AskPenny llmOk={!!llm?.ok} />
          </div>

          {agentsOn && (
            <AgentPanel
              refreshKey={agentRefresh}
              ghostNames={Object.fromEntries(scan.ghosts.map((g) => [g.id, g.display_name]))}
            />
          )}
          {me?.auth_enabled && !me.logged_in && (
            <p className="card login-line">
              Log in to let Penny send emails for you. Everything else works offline.
            </p>
          )}
          <HowWeDecide />
          <Graveyard
            ghosts={buried}
            saved={scan.saved_yearly_cents}
            currency={scan.currency}
            fresh={fresh}
            onUndo={(id) => setStatus(id, 'active')}
          />
          <footer className="footer muted small">
            AI explains, code finds, you decide. Gemma runs locally in Ollama. Ghost Bills never
            sends email, opens links or contacts any company.
          </footer>
        </main>
      )}

      {importing && (
        <ImportDialog
          onClose={() => setImporting(false)}
          onDone={async () => {
            setImporting(false)
            setSelected(null)
            const s = await refresh()
            enrich(s, llm)
          }}
        />
      )}
      {seance && scan && (
        <Seance
          ghosts={counted}
          total={scan.total_ghost_yearly_cents}
          currency={scan.currency}
          onClose={() => setSeance(false)}
        />
      )}
    </div>
  )
}
