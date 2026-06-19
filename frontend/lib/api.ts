// Helper for authenticated calls to the FastAPI backend. The backend verifies
// the Supabase access token and derives the user_id from it.
export const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

// On-brand, calm message shown when the backend can't be reached or is having a
// moment — instead of a raw "Failed to fetch" / 502.
export const BACKEND_UNREACHABLE =
  "Our assistant has wandered off for a coffee. Give it a moment and try again.";

export async function backendPost<T>(
  path: string,
  accessToken: string,
  body: unknown,
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BACKEND_URL}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify(body),
    });
  } catch {
    // Network error / backend down — never surface the raw fetch error.
    throw new Error(BACKEND_UNREACHABLE);
  }

  if (!res.ok) {
    // Backend up but unavailable (gateway/config/agent) — keep it friendly.
    if (res.status >= 500) {
      throw new Error(BACKEND_UNREACHABLE);
    }
    // Actionable client errors (auth, validation) — show the real reason.
    let detail = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      if (data?.detail) detail = data.detail;
    } catch {
      // non-JSON error body; keep the default message
    }
    throw new Error(detail);
  }

  return (await res.json()) as T;
}
