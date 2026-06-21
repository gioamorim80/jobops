"use client";

import { useState } from "react";

import { backendPost } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString();
  } catch {
    return "";
  }
}

// Marks one of the user's own tailorings as applied / not applied via the
// authenticated backend endpoint (which scopes the write to this user's row).
export function AppliedToggle({
  id,
  appliedAt: initial,
}: {
  id: string;
  appliedAt: string | null;
}) {
  const [appliedAt, setAppliedAt] = useState<string | null>(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);

  async function toggle() {
    setBusy(true);
    setError(false);
    try {
      const supabase = createClient();
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session) throw new Error("Your session expired.");
      const res = await backendPost<{ ok: boolean; applied_at: string | null }>(
        "/ondemand/applied",
        session.access_token,
        { id, applied: appliedAt === null },
      );
      setAppliedAt(res.applied_at);
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  }

  if (appliedAt) {
    return (
      <span className="applied">
        <span className="badge applied-badge">
          Applied ✓ {formatDate(appliedAt)}
        </span>
        <button
          type="button"
          className="linklike"
          onClick={toggle}
          disabled={busy}
          aria-label="Un-mark as applied"
        >
          {busy ? "…" : "Un-mark"}
        </button>
      </span>
    );
  }

  return (
    <button
      type="button"
      className="linklike"
      onClick={toggle}
      disabled={busy}
      aria-label="Mark as applied"
    >
      {busy ? "…" : error ? "Retry" : "Mark as applied"}
    </button>
  );
}
