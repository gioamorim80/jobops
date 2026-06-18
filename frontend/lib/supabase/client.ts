import { createBrowserClient } from "@supabase/ssr";

// Browser client — uses the public anon key only. The service_role key must
// never be referenced anywhere in the frontend.
export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  );
}
