import Link from "next/link";
import { notFound } from "next/navigation";

import { ScoredResult } from "@/components/ScoredResult";
import { createClient } from "@/lib/supabase/server";
import type { ScoreResult, TailoredBullet } from "@/lib/types";

export default async function ScoredDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const supabase = await createClient();

  // RLS: this returns a row only if it belongs to the signed-in user;
  // anyone else's id simply yields nothing → 404.
  const { data: row } = await supabase
    .from("tailorings")
    .select("id, score, tailored_bullets, analysis, approved")
    .eq("id", id)
    .maybeSingle();

  const score = (row?.score ?? null) as ScoreResult | null;
  if (!row || !score) notFound();

  const bullets = (row.tailored_bullets ?? []) as TailoredBullet[];

  return (
    <div style={{ maxWidth: 720 }}>
      <div className="section-head">
        <h1 style={{ margin: 0 }}>Saved result</h1>
        <Link href="/dashboard" className="btn btn-ghost btn-sm">
          Back
        </Link>
      </div>

      <ScoredResult
        score={score}
        bullets={bullets}
        analysis={row.analysis ?? ""}
        approved={!!row.approved}
      />

      <div style={{ marginTop: "1.25rem" }}>
        <Link href="/score" className="btn btn-secondary btn-sm">
          Score another job
        </Link>
      </div>
    </div>
  );
}
