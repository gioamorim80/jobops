"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { backendPost } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

// Deletes one of the user's own matches. `matches` is SELECT-only to the client
// (service role is the only writer), so this goes through the backend endpoint,
// which scopes the delete to the verified JWT user — no user_id is sent. UX mirrors
// the Dashboard's DeleteTailoringButton: inline confirm, busy + retry states,
// then router.refresh() to re-query and drop the row.
export function DeleteMatchButton({ id }: { id: string }) {
  const router = useRouter();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);

  async function remove() {
    setBusy(true);
    setError(false);
    try {
      const supabase = createClient();
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session) throw new Error("Your session expired.");
      await backendPost("/matches/delete", session.access_token, { id });
      router.refresh();
    } catch {
      setError(true);
      setBusy(false);
      setConfirming(false);
    }
  }

  if (confirming) {
    return (
      <span className="scored-actions">
        <button
          type="button"
          className="linklike danger"
          onClick={remove}
          disabled={busy}
        >
          {busy ? "Deleting…" : "Delete?"}
        </button>
        <button
          type="button"
          className="linklike"
          onClick={() => setConfirming(false)}
          disabled={busy}
        >
          Cancel
        </button>
      </span>
    );
  }

  return (
    <button
      type="button"
      className="linklike"
      aria-label="Delete this match"
      onClick={() => setConfirming(true)}
    >
      {error ? "Retry delete" : "Delete"}
    </button>
  );
}
