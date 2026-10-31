import type { Me } from '../api'
import { Mascot } from '../Mascot'

interface Props {
  me: Me | null
  onImport: () => void
}

export function Header({ me, onImport }: Props) {
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
      {me?.auth_enabled &&
        (me.logged_in ? (
          <span className="who">
            <span className="mono small">{me.name}</span>
            {/* Full page navigations: the Auth0 SDK owns these routes. */}
            <a className="btn btn-secondary" href="/auth/logout">
              Log out
            </a>
          </span>
        ) : (
          <a className="btn btn-secondary" href="/auth/login">
            Log in
          </a>
        ))}
      <button className="btn btn-primary" onClick={onImport}>
        Import statement
      </button>
    </header>
  )
}
