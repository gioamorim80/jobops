"use client";

import { useState } from "react";

import { backendPost } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import type { Proposal } from "@/lib/types";

// Human-readable lines for a proposed profile change (only the fields that change).
function changeLines(c: Proposal["changes"]): string[] {
  const lines: string[] = [];
  if (c.add_skills.length) lines.push(`Add skills: ${c.add_skills.join(", ")}`);
  if (c.add_domains.length)
    lines.push(`Add domains: ${c.add_domains.join(", ")}`);
  if (c.add_target_roles.length)
    lines.push(`Add target roles: ${c.add_target_roles.join(", ")}`);
  if (c.add_attribution_notes.length)
    lines.push(`Attribution note: ${c.add_attribution_notes.join(" · ")}`);
  if (c.set_seniority) lines.push(`Set seniority: ${c.set_seniority}`);
  if (c.set_remote_pref)
    lines.push(`Set remote preference: ${c.set_remote_pref}`);
  return lines;
}

// Renders a coach-proposed profile change with the human-confirm gate. Owns the
// /enrich/apply call and its own applying/applied state so any caller (the Coach,
// the score page) gets the SAME confirm flow without re-implementing it. Reports
// outcomes to the parent: onApplied after a successful save, onDismiss on "Not now".
// Apply errors are routed out via onError (so the caller shows them wherever it
// already shows errors), not rendered inline — keeping callers in control of error
// placement. The apply merges via the existing backend; nothing is written until the
// user clicks "Add to profile".
export function ProposalCard({
  proposal,
  onApplied,
  onDismiss,
  onError,
}: {
  proposal: Proposal;
  onApplied?: () => void;
  onDismiss: () => void;
  onError?: (message: string) => void;
}) {
  const [applying, setApplying] = useState(false);
  const [applied, setApplied] = useState(false);

  async function confirm() {
    setApplying(true);
    onError?.("");
    try {
      const supabase = createClient();
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session)
        throw new Error("Your session expired. Please sign in again.");
      await backendPost("/enrich/apply", session.access_token, {
        changes: proposal.changes,
      });
      setApplied(true);
      onApplied?.();
    } catch (err) {
      onError?.(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setApplying(false);
    }
  }

  return (
    <div className="proposal">
      <div className="proposal-title">Proposed update</div>
      {proposal.summary && (
        <p className="muted" style={{ margin: "0 0 0.6rem" }}>
          {proposal.summary}
        </p>
      )}
      <ul className="list-clean">
        {changeLines(proposal.changes).map((line, i) => (
          <li key={i}>{line}</li>
        ))}
      </ul>
      {applied ? (
        <p className="proposal-saved">Saved to your profile.</p>
      ) : (
        <>
          <p className="hint" style={{ margin: "0 0 0.6rem" }}>
            Want it shorter or different? Just reply below and I&apos;ll revise
            it before you save.
          </p>
          <div className="proposal-actions">
            <button
              type="button"
              className="btn btn-sm"
              onClick={confirm}
              disabled={applying}
            >
              {applying ? "Saving…" : "Add to profile"}
            </button>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={onDismiss}
              disabled={applying}
            >
              Not now
            </button>
          </div>
        </>
      )}
    </div>
  );
}
