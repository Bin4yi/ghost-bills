import type { Question } from '../api'
import { Mascot } from '../Mascot'

interface Props {
  questions: Question[]
  onAnswer: (id: string, choice: 'a' | 'b' | null) => void
}

export function QuestionCards({ questions, onAnswer }: Props) {
  if (questions.length === 0) return null
  const open = questions.filter((q) => q.answer === null).length
  return (
    <section className="questions" aria-labelledby="questions-title">
      <div className="questions-head">
        <Mascot name="penny_question" size={64} />
        <div>
          <h2 id="questions-title" className="section-title">
            {open > 0
              ? `Penny has ${open} question${open === 1 ? '' : 's'}`
              : 'Penny remembers your answers'}
          </h2>
          <p className="muted">I ask you instead of guessing.</p>
        </div>
      </div>
      <div className="question-list">
        {questions.map((q) => (
          <article key={q.id} className="card question">
            <span className="tag">{q.tag}</span>
            <h3>{q.question}</h3>
            <p className="muted small">{q.why}</p>
            {q.answer === null ? (
              <div className="row">
                <button className="btn btn-primary" onClick={() => onAnswer(q.id, 'a')}>
                  {q.choice_a}
                </button>
                <button className="btn btn-secondary" onClick={() => onAnswer(q.id, 'b')}>
                  {q.choice_b}
                </button>
              </div>
            ) : (
              <div className="row answered">
                <p>
                  You said: <strong>{q.answer === 'a' ? q.choice_a : q.choice_b}</strong>. I will
                  remember.
                </p>
                <button className="btn btn-secondary btn-small" onClick={() => onAnswer(q.id, null)}>
                  Change
                </button>
              </div>
            )}
          </article>
        ))}
      </div>
    </section>
  )
}
