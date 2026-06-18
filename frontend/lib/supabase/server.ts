import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

// Server client for Server Components and Route Handlers. Anon key only;
// RLS enforces tenant isolation on every query.
export async function createClient() {
  const cookieStore = await cookies();

  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options),
            );
          } catch {
            // Called from a Server Component (read-only cookies). The session
            // is refreshed in middleware, so this is safe to ignore.
          }
        },
      },
    },
  );
}
