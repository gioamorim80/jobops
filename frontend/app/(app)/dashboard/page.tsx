import Link from "next/link";
import { redirect } from "next/navigation";

import { AppliedToggle } from "@/components/AppliedToggle";
import { DeleteTailoringButton } from "@/components/DeleteTailoringButton";
import { createClient } from "@/lib/supabase/server";
import type { ParsedProfile, ScoreResult } from "@/lib/types";
import { decisionClass, jobLabel } from "@/lib/ui";

function ChipList({ items, empty }: { items: string[]; empty: string }) {
  if (!items || items.length === 0) {
    return <span className="faint">{empty}</span>;
  }
  return (
    <div className="chips">
      {items.map((item) => (
        <span key={item} className="chip">
          {item}
        </span>
      ))}
    </div>
  );
}

export default async function DashboardPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // RLS guarantees this only ever returns the signed-in user's own row.
  const { data: profile } = await supabase
    .from("profiles")
    .select("full_name, email, parsed, resume_file_path, onboarding_complete")
    .eq("user_id", user!.id)
    .maybeSingle();

  if (!profile?.onboarding_complete) {
    redirect("/onboarding");
  }

  const parsed = (profile.parsed ?? {}) as Partial<ParsedProfile>;
  const resumeName = profile.resume_file_path?.split("/").pop() ?? "—";

  // RLS scopes this to the signed-in user's own tailorings only. We select "*"
  // (rather than naming role/company explicitly) so the fetch never 400s if the
  // 0006 columns aren't present yet — an errored select returns null, which would
  // otherwise render as a misleading "No scored jobs yet". role/company are read
  // defensively by jobLabel, so rows missing them still show with a fallback.
  const { data: tailorings, error: tailoringsError } = await supabase
    .from("tailorings")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(20);

  if (tailoringsError) {
    console.error("Failed to load tailorings:", tailoringsError.message);
  }

  return (
    <div>
      <div className="section-head">
        <div>
          <h1 style={{ marginBottom: "0.25rem" }}>
            {profile.full_name || "Your profile"}
          </h1>
          <p className="muted" style={{ margin: 0 }}>
            {profile.email || "No email on file"}
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap" }}>
          <Link href="/score" className="btn btn-sm">
            Score a job
          </Link>
          <Link href="/settings" className="btn btn-secondary btn-sm">
            Edit profile
          </Link>
        </div>
      </div>

      <div className="card">
        <div className="card-title">Profile</div>
        <div className="summary-grid">
          <div className="summary-item">
            <div className="label">Target roles</div>
            <ChipList items={parsed.target_roles ?? []} empty="None set yet" />
          </div>
          <div className="summary-item">
            <div className="label">Seniority</div>
            <div>{parsed.seniority || <span className="faint">—</span>}</div>
          </div>
          <div className="summary-item">
            <div className="label">Remote preference</div>
            <div>{parsed.remote_pref || <span className="faint">—</span>}</div>
          </div>
          <div className="summary-item">
            <div className="label">Locations</div>
            <ChipList items={parsed.locations ?? []} empty="—" />
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-title">Skills &amp; domains</div>
        <div className="field">
          <div className="label">Skills</div>
          <ChipList items={parsed.skills ?? []} empty="None extracted" />
        </div>
        <div className="field" style={{ marginBottom: 0 }}>
          <div className="label">Domains</div>
          <ChipList items={parsed.domains ?? []} empty="None extracted" />
        </div>
      </div>

      <div className="card">
        <div className="card-title">Resume</div>
        <p className="muted" style={{ margin: 0 }}>
          On file: <span className="file-name">{resumeName}</span>
        </p>
        <p className="faint" style={{ marginTop: "0.5rem" }}>
          Stored privately. Only you can access it.
        </p>
        <Link
          href="/onboarding"
          className="btn btn-ghost btn-sm"
          style={{ marginTop: "0.5rem" }}
        >
          Replace resume
        </Link>
      </div>

      <div className="card">
        <div className="card-title">Scored jobs</div>
        {!tailorings || tailorings.length === 0 ? (
          <p className="faint" style={{ margin: 0 }}>
            No scored jobs yet. <Link href="/score">Score your first</Link>.
          </p>
        ) : (
          <div className="scored-list">
            {tailorings.map((t) => {
              const s = (t.score ?? {}) as Partial<ScoreResult>;
              return (
                <div key={t.id} className="scored-item">
                  <Link href={`/scored/${t.id}`} className="scored-link">
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
                      <span className="faint">
                        {new Date(t.created_at).toLocaleDateString()}
                      </span>
                    </span>
                  </Link>
                  <span className="scored-actions">
                    {t.source_url && (
                      <a
                        href={t.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="linklike"
                      >
                        View posting →
                      </a>
                    )}
                    <AppliedToggle id={t.id} appliedAt={t.applied_at ?? null} />
                    <DeleteTailoringButton id={t.id} />
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
