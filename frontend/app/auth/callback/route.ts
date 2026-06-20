import { NextResponse } from "next/server";
import type { EmailOtpType } from "@supabase/supabase-js";
import type { SupabaseClient } from "@supabase/supabase-js";

import { createClient } from "@/lib/supabase/server";

// Where to land a freshly-authenticated user: onboarding if they have no
// completed profile yet, otherwise the Home hub. Reads only the authenticated
// user's own profile state (RLS-scoped).
async function postLoginDestination(supabase: SupabaseClient): Promise<string> {
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return "/login";

  const { data: profile } = await supabase
    .from("profiles")
    .select("onboarding_complete")
    .eq("user_id", user.id)
    .maybeSingle();

  return profile?.onboarding_complete ? "/home" : "/onboarding";
}

// Magic-link landing. Supabase sends either a PKCE `code` or a `token_hash`;
// handle both, then route by the user's profile state.
export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  const tokenHash = searchParams.get("token_hash");
  const type = searchParams.get("type") as EmailOtpType | null;
  const next = searchParams.get("next"); // honored if a deep link was requested

  const supabase = await createClient();

  let authed = false;
  if (code) {
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    authed = !error;
  } else if (tokenHash && type) {
    const { error } = await supabase.auth.verifyOtp({
      type,
      token_hash: tokenHash,
    });
    authed = !error;
  }

  if (!authed) {
    return NextResponse.redirect(`${origin}/login?error=auth`);
  }

  const destination = next ?? (await postLoginDestination(supabase));
  return NextResponse.redirect(`${origin}${destination}`);
}
