import type { ReactNode } from "react";
import { redirect } from "next/navigation";

import { AppHeader } from "@/components/AppHeader";
import { createClient } from "@/lib/supabase/server";

// Server-side guard for the whole authenticated shell. Middleware also blocks
// unauthenticated access; this is the defence-in-depth layer and gives us the
// user for the header.
export default async function AppLayout({ children }: { children: ReactNode }) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // Logged-out visitors to a shared app link land on the public marketing page
  // (which has its own Sign in / Get started CTAs), not the bare /login form.
  if (!user) redirect("/");

  return (
    <>
      <AppHeader email={user.email ?? ""} />
      <main className="container app-main">{children}</main>
    </>
  );
}
