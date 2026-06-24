"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

// The five top-nav destinations. The brand logo (/home) is intentionally NOT here,
// so being on /home highlights nothing in the nav.
const NAV_LINKS: { href: string; label: string }[] = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/matches", label: "Matches" },
  { href: "/score", label: "Score a job" },
  { href: "/coach", label: "Coach" },
  { href: "/settings", label: "Settings" },
];

// Client subcomponent so the rest of AppHeader can stay a server component: only
// the active-route comparison needs usePathname().
export function NavLinks() {
  const pathname = usePathname();
  return (
    <nav className="app-nav">
      {NAV_LINKS.map(({ href, label }) => {
        // Exact match handles today's flat routes; startsWith covers future
        // sub-routes (e.g. /matches/[id]).
        const active = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
          >
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
