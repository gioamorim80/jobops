import Link from "next/link";
import { redirect } from "next/navigation";

import { createClient } from "@/lib/supabase/server";
import type { ParsedProfile } from "@/lib/types";

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
        <Link href="/settings" className="btn btn-secondary btn-sm">
          Edit profile
        </Link>
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
        <div className="card-title">Résumé</div>
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
          Replace résumé
        </Link>
      </div>
    </div>
  );
}
