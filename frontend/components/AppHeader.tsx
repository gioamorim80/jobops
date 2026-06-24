import Link from "next/link";

import { NavLinks } from "@/components/NavLinks";

export function AppHeader({ email }: { email: string }) {
  return (
    <header className="app-header">
      <div className="container app-header-inner">
        <Link href="/home" className="brand">
          JobOps
        </Link>
        <NavLinks />
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
