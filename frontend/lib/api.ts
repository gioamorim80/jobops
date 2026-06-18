// Helper for authenticated calls to the FastAPI backend. The backend verifies
// the Supabase access token and derives the user_id from it.
export const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export async function backendPost<T>(
  path: string,
  accessToken: string,
  body: unknown,
): Promise<T> {
  const res = await fetch(`${BACKEND_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
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
