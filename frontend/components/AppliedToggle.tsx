"use client";

import { useState } from "react";

import { backendPost } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

// applied_at is stored at noon UTC, so reading UTC parts gives the calendar day
// the user picked, regardless of their timezone.
function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, { timeZone: "UTC" });
  } catch {
    return "";
  }
}

function isoToInput(iso: string): string {
  const d = new Date(iso);
  const m = String(d.getUTCMonth() + 1).padStart(2, "0");
  const day = String(d.getUTCDate()).padStart(2, "0");
  return `${d.getUTCFullYear()}-${m}-${day}`;
}

function todayInput(): string {
  const d = new Date();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

// Marks one of the user's own tailorings as applied / not applied via the
// authenticated backend endpoint (which scopes the write to this user's row).
// The applied date is editable: it defaults to today when marking, and the
// "Applied ✓ <date>" badge can be edited afterward.
export function AppliedToggle({
  id,
  appliedAt: initial,
}: {
  id: string;
  appliedAt: string | null;
}) {
  const [appliedAt, setAppliedAt] = useState<string | null>(initial);
  const [draft, setDraft] = useState<string | null>(null); // editing when non-null
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);

  async function save() {
    if (!draft) return;
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
        { id, applied: true, applied_on: draft },
      );
      setAppliedAt(res.applied_at);
      setDraft(null);
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  }

  async function unmark() {
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
        { id, applied: false },
      );
      setAppliedAt(res.applied_at);
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  }

  // Editing the date (when first marking, or correcting an existing badge).
  if (draft !== null) {
    return (
      <span className="applied-edit">
        <input
          type="date"
          className="input input-date"
          value={draft}
          max={todayInput()}
          disabled={busy}
          aria-label="Date applied"
          onChange={(e) => setDraft(e.target.value)}
        />
        <button
          type="button"
          className="linklike"
          onClick={save}
          disabled={busy || !draft}
        >
          {busy ? "…" : error ? "Retry" : "Save"}
        </button>
        <button
          type="button"
          className="linklike muted"
          onClick={() => {
            setDraft(null);
            setError(false);
          }}
          disabled={busy}
        >
          Cancel
        </button>
      </span>
    );
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
          onClick={() => setDraft(isoToInput(appliedAt))}
          disabled={busy}
          aria-label="Edit applied date"
        >
          Edit date
        </button>
        <button
          type="button"
          className="linklike muted"
          onClick={unmark}
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
      onClick={() => {
        setDraft(todayInput());
        setError(false);
      }}
      disabled={busy}
      aria-label="Mark as applied"
    >
      Mark as applied
    </button>
  );
}
