import Link from "next/link";
import { redirect } from "next/navigation";

import { createClient } from "@/lib/supabase/server";
import type { Match } from "@/lib/types";
import { jobLabel } from "@/lib/ui";

function MiniList({ items, empty }: { items: string[] | null; empty: string }) {
  if (!items || items.length === 0) return <p className="faint">{empty}</p>;
  return (
    <ul className="list-clean">
      {items.map((item, i) => (
        <li key={i}>{item}</li>
      ))}
    </ul>
  );
}

export default async function MatchesPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const { data: profile } = await supabase
    .from("profiles")
    .select("onboarding_complete")
    .eq("user_id", user!.id)
    .maybeSingle();

  if (!profile?.onboarding_complete) {
    redirect("/onboarding");
  }

  // RLS scopes matches to the signed-in user; the job it points at is embedded
  // from the shared pool. Highest fit first.
  const { data, error } = await supabase
    .from("matches")
    .select(
      "id, score, band, cleared, gaps, analysis, posted_at, jobs ( title, company, location_display, source_url )",
    )
    .order("score", { ascending: false })
    .limit(50);

  if (error) {
    console.error("Failed to load matches:", error.message);
  }
  const matches = (data ?? []) as unknown as Match[];

  return (
    <div>
      <div className="section-head">
        <div>
          <h1 style={{ marginBottom: "0.25rem" }}>Matches</h1>
          <p className="muted" style={{ margin: 0 }}>
            Jobs we found and scored for you. This is separate from the jobs you
            score yourself, which live on your Dashboard.
          </p>
        </div>
        <Link href="/dashboard" className="btn btn-secondary btn-sm">
          Dashboard
        </Link>
      </div>

      {matches.length === 0 ? (
        <div className="card">
          <p className="faint" style={{ margin: 0 }}>
            No matches yet. New scored jobs will show up here once a scan has run.
          </p>
        </div>
      ) : (
        matches.map((m) => {
          const job = m.jobs;
          return (
            <div key={m.id} className="card">
              <div className="section-head" style={{ marginBottom: "0.6rem" }}>
                <div>
                  <div className="card-title" style={{ marginBottom: "0.15rem" }}>
                    {jobLabel(job?.title ?? null, job?.company ?? null, job?.source_url ?? null)}
                  </div>
                  {job?.location_display && (
                    <p className="muted" style={{ margin: 0 }}>
                      {job.location_display}
                    </p>
                  )}
                </div>
                <div className="scored-meta">
                  <span className="scored-fit">{m.score ?? "—"}</span>
                  {m.band && <span className="band">{m.band}</span>}
                </div>
              </div>

              {m.analysis && <p style={{ marginTop: 0 }}>{m.analysis}</p>}

              <div className="summary-grid">
                <div className="summary-item">
                  <div className="label">Requirements you clear</div>
                  <MiniList items={m.cleared} empty="Nothing clearly cleared." />
                </div>
                <div className="summary-item">
                  <div className="label">Honest gaps</div>
                  <MiniList items={m.gaps} empty="No notable gaps." />
                </div>
              </div>

              <div className="scored-actions" style={{ marginTop: "1rem" }}>
                {job?.source_url && (
                  <a
                    href={job.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="linklike"
                  >
                    View posting →
                  </a>
                )}
                {job?.source_url && (
                  <Link
                    href={`/score?url=${encodeURIComponent(job.source_url)}`}
                    className="btn btn-sm"
                  >
                    Tailor my resume for this
                  </Link>
                )}
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}
