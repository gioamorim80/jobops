import Link from "next/link";
import { redirect } from "next/navigation";

import { createClient } from "@/lib/supabase/server";
import type { ScoreResult } from "@/lib/types";
import { decisionClass, jobLabel } from "@/lib/ui";

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
  const greeting = firstName
    ? `Hi ${firstName} — what would you like to do?`
    : "What would you like to do?";

  // A small peek only (max 3) — not the full list. RLS scopes to this user.
  // Select "*" so the fetch can't 400 if the 0006 role/company columns aren't
  // present yet (an errored select returns null and the peek would vanish);
  // jobLabel reads role/company defensively.
  const { data: recent, error: recentError } = await supabase
    .from("tailorings")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(3);

  if (recentError) {
    console.error("Failed to load recent tailorings:", recentError.message);
  }

  return (
    <div>
      <h1>{greeting}</h1>

      <div className="launcher-grid">
        <Link href="/score" className="card launcher-card">
          <div className="card-title">Score a new job</div>
          <p className="muted">
            Paste a link or the posting text for an honest fit score and
            suggested resume edits.
          </p>
        </Link>
        <Link href="/dashboard" className="card launcher-card">
          <div className="card-title">Edit my profile</div>
          <p className="muted">
            See and update your profile — skills, preferences, and how your
            experience is framed — so every score reflects the real you.
          </p>
        </Link>
        <Link href="/coach" className="card launcher-card">
          <div className="card-title">Chat with the Coach</div>
          <p className="muted">
            Add the true context your resume missed. Warm and in-scope — nothing
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
                      {jobLabel(t.role, t.company, t.source_url)}
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
