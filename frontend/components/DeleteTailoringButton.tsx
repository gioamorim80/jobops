"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { createClient } from "@/lib/supabase/client";

// Deletes one of the user's own saved tailorings, with a small inline confirm.
// RLS (user_id = auth.uid()) guarantees a user can only ever delete their own
// rows, so no user_id is sent from the client.
export function DeleteTailoringButton({ id }: { id: string }) {
  const router = useRouter();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);

  async function remove() {
    setBusy(true);
    setError(false);
    const supabase = createClient();
    const { error } = await supabase.from("tailorings").delete().eq("id", id);
    if (error) {
      setError(true);
      setBusy(false);
      setConfirming(false);
      return;
    }
    router.refresh();
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
      aria-label="Delete this saved result"
      onClick={() => setConfirming(true)}
    >
      {error ? "Retry delete" : "Delete"}
    </button>
  );
}
