import Link from "next/link";
import { redirect } from "next/navigation";

import { createClient } from "@/lib/supabase/server";
import type { ScoreResult } from "@/lib/types";
import { decisionClass, jobSnippet } from "@/lib/ui";

// A light launcher / hub — routes into the existing pages. The detailed views
// (full profile + scored-jobs list) live on the Dashboard; Home only launches.
export default async function HomePage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const { data: profile } = await supabase
    .from("profiles")
    .select("full_name, onboarding_complete")
    .eq("user_id", user!.id)
    .maybeSingle();

  if (!profile?.onboarding_complete) {
    redirect("/onboarding");
  }

  const firstName = (profile.full_name ?? "").trim().split(" ")[0];

  // A small peek only (max 3) — not the full list. RLS scopes to this user.
  const { data: recent } = await supabase
    .from("tailorings")
    .select("id, source_url, job_text, score")
    .order("created_at", { ascending: false })
    .limit(3);

  return (
    <div>
      <h1 style={{ marginBottom: "0.25rem" }}>
        {firstName ? `Olá, ${firstName} — ` : "Olá — "}what would you like to
        do?
      </h1>
      <p className="muted">Pick a place to start. Your search, at your pace.</p>

      <div className="launcher-grid">
        <Link href="/score" className="card launcher-card">
          <div className="card-title">Score a new job</div>
          <p className="muted">
            Paste a link or the posting text for an honest fit score and
            suggested résumé edits.
          </p>
        </Link>
        <Link href="/dashboard" className="card launcher-card">
          <div className="card-title">Review my scored jobs</div>
          <p className="muted">
            Revisit everything you&apos;ve scored — fit, decision, and the
            suggestions you saved.
          </p>
        </Link>
        <Link href="/coach" className="card launcher-card">
          <div className="card-title">Chat with the Coach</div>
          <p className="muted">
            Add the true context your résumé missed. Warm and in-scope — nothing
            saved unless you confirm.
          </p>
        </Link>
      </div>

      {recent && recent.length > 0 && (
        <div className="card" style={{ marginTop: "1.5rem" }}>
          <div className="section-head" style={{ marginBottom: "1rem" }}>
            <div className="card-title" style={{ margin: 0 }}>
              Recently scored
            </div>
            <Link href="/dashboard" className="faint">
              See all
            </Link>
          </div>
          <div className="scored-list">
            {recent.map((t) => {
              const s = (t.score ?? {}) as Partial<ScoreResult>;
              return (
                <Link
                  key={t.id}
                  href={`/scored/${t.id}`}
                  className="scored-item"
                >
                  <span className="scored-link">
                    <span className="snippet">
                      {jobSnippet(t.job_text, t.source_url)}
                    </span>
                    <span className="scored-meta">
                      <span className="scored-fit">{s.fit ?? "—"}</span>
                      {s.decision && (
                        <span className={decisionClass[s.decision]}>
                          {s.decision}
                        </span>
                      )}
                    </span>
                  </span>
                </Link>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
