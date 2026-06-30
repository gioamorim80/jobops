"use client";

import type { ScoreResult, TailoredBullet } from "@/lib/types";
import { decisionClass, fitBand } from "@/lib/ui";

function List({ items, empty }: { items: string[]; empty: string }) {
  if (!items?.length) return <p className="faint">{empty}</p>;
  return (
    <ul className="list-clean">
      {items.map((item, i) => (
        <li key={i}>{item}</li>
      ))}
    </ul>
  );
}

// Render of a saved tailoring (history detail). Now a client component so the
// upcoming commits can add interactive blocks (the on-demand Tailor button and
// the "Something's missing?" coach block) that hold local state. The job
// reference (id, source_url, job_text, role, company) is plumbed in now so those
// blocks have what they need — id + job_text to tailor on demand, source_url to
// force a re-score — without another prop or route change. Those fields are
// intentionally not rendered yet: this commit's output is identical to before.
// The editable variant lives in the /score page.
export function ScoredResult({
  score,
  bullets,
  analysis,
  approved,
}: {
  id: string;
  source_url: string | null;
  job_text: string | null;
  role: string | null;
  company: string | null;
  score: ScoreResult;
  bullets: TailoredBullet[];
  analysis: string;
  approved: boolean;
}) {
  return (
    <>
      <div className="card">
        <div className="score-head">
          <span className="score-num">
            {score.fit}
            <small>/100</small>
          </span>
          <span className="band">{fitBand(score.fit)}</span>
          <span className={decisionClass[score.decision] ?? "decision"}>
            Decision: {score.decision}
          </span>
          {approved && (
            <span className="decision decision-apply">Approved</span>
          )}
        </div>
        {score.pitch && <p style={{ marginTop: "1rem" }}>{score.pitch}</p>}
        {score.referral_angle && (
          <p className="muted" style={{ marginBottom: 0 }}>
            <strong>Referral angle:</strong> {score.referral_angle}
          </p>
        )}
      </div>

      <div className="card">
        <div className="card-title">Requirements you clear</div>
        <List items={score.cleared} empty="Nothing clearly cleared." />
      </div>

      <div className="card">
        <div className="card-title">Honest gaps</div>
        <List items={score.gaps} empty="No notable gaps." />
      </div>

      <div className="card">
        <div className="card-title">Suggested changes to your resume</div>
        {bullets.length === 0 && (
          <p className="faint">No suggestions were saved.</p>
        )}
        {bullets.map((b, i) => (
          <div key={i} className="bullet">
            {b.where && <p className="where">{b.where}</p>}
            {b.original && <p className="orig">Currently: {b.original}</p>}
            <p style={{ margin: 0 }}>{b.tailored}</p>
            {b.why && <p className="why">Why: {b.why}</p>}
          </div>
        ))}
      </div>

      {analysis && (
        <div className="card">
          <div className="card-title">Match analysis</div>
          <p className="muted" style={{ margin: 0 }}>
            {analysis}
          </p>
        </div>
      )}
    </>
  );
}
