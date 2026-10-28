import { Mascot } from '../Mascot'

export function Header({ onImport }: { onImport: () => void }) {
  return (
    <header className="header">
      <div className="brand">
        <Mascot name="logo_mark" size={48} />
        <h1 className="logo">
          Ghost <em className="logo-bills">Bills</em>
        </h1>
      </div>
      <p className="lock-pill">
        <span aria-hidden="true">🔒</span> Your bank data stays on this laptop.
      </p>
      <button className="btn btn-primary" onClick={onImport}>
        Import statement
      </button>
    </header>
  )
}
