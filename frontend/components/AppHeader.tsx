import Link from "next/link";

export function AppHeader({ email }: { email: string }) {
  return (
    <header className="app-header">
      <div className="container app-header-inner">
        <Link href="/dashboard" className="brand">
          JobOps
        </Link>
        <nav className="app-nav">
          <Link href="/dashboard">Dashboard</Link>
          <Link href="/score">Score a job</Link>
          <Link href="/settings">Settings</Link>
        </nav>
        <div className="app-header-right">
          <span className="user-email">{email}</span>
          <form action="/auth/signout" method="post">
            <button type="submit" className="btn btn-ghost btn-sm">
              Sign out
            </button>
          </form>
        </div>
      </div>
    </header>
  );
}
