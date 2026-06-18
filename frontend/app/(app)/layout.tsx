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

  if (!user) redirect("/login");

  return (
    <>
      <AppHeader email={user.email ?? ""} />
      <main className="container app-main">{children}</main>
    </>
  );
}
