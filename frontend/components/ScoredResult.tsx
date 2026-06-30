"use client";

import { useState } from "react";

import { backendPost } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import type { ScoreResult, TailorResponse, TailoredBullet } from "@/lib/types";
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
  id,
  score,
  bullets: initialBullets,
  analysis: initialAnalysis,
  approved: initialApproved,
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
  // Local state seeded from the saved row. Tailoring on demand updates these in
  // place so the read-only view flips from "not tailored yet" to showing the
  // saved suggestions without a reload. source_url/job_text/role/company stay
  // declared for the re-score block in the next commit; the tailor call is
  // id-only (the backend resolves the job text from the user-scoped row).
  const [bullets, setBullets] = useState<TailoredBullet[]>(initialBullets);
  const [analysis, setAnalysis] = useState(initialAnalysis);
  const [approved, setApproved] = useState(initialApproved);
  const [tailoring, setTailoring] = useState(false);
  // Latched true only on a cap (limit_reached) response, so the button can't be
  // clicked into the cap again. Not set by no_profile or network errors.
  const [tailorCapped, setTailorCapped] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  async function token(): Promise<string> {
    const supabase = createClient();
    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (!session)
      throw new Error("Your session expired. Please sign in again.");
    return session.access_token;
  }

  // Mirrors the live /score page's tailorResume(): one id-only call to
  // /ondemand/tailor. The button is only offered when no tailoring exists yet
  // (see the gating in the card below), so the paid step runs at most once.
  async function tailorResume() {
    if (!id) return;
    setTailoring(true);
    setError("");
    setNotice("");
    try {
      const data = await backendPost<TailorResponse>(
        "/ondemand/tailor",
        await token(),
        { id },
      );
      if (data.status !== "ok") {
        // A cap (daily or monthly tailor cap) latches the button off and shows
        // the friendly notice; other non-ok statuses (e.g. no_profile) leave it
        // clickable and route the reason to the error display.
        if (data.status === "limit_reached") {
          setTailorCapped(true);
          setNotice(data.message);
        } else {
          setError(data.message);
        }
        return;
      }
      setBullets(data.tailor.tailored_bullets);
      setAnalysis(data.tailor.analysis);
      setApproved(data.approved);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setTailoring(false);
    }
  }

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
        {bullets.length === 0 ? (
          <>
            <p className="hint" style={{ marginTop: 0, marginBottom: "1rem" }}>
              Scoring is done. When you want to apply, generate suggested resume
              changes from your real experience. They&apos;re reordered and
              rephrased, never invented, so run this only for jobs you mean to
              pursue.
            </p>
            {notice && (
              <div
                className="alert alert-info"
                style={{ marginBottom: "1rem" }}
              >
                {notice}
              </div>
            )}
            {error && (
              <div
                className="alert alert-error"
                style={{ marginBottom: "1rem" }}
              >
                {error}
              </div>
            )}
            <button
              type="button"
              className="btn"
              onClick={tailorResume}
              disabled={tailoring || tailorCapped}
            >
              {tailoring ? (
                <>
                  <span className="spinner" /> Tailoring…
                </>
              ) : (
                "Tailor my resume for this"
              )}
            </button>
          </>
        ) : (
          bullets.map((b, i) => (
            <div key={i} className="bullet">
              {b.where && <p className="where">{b.where}</p>}
              {b.original && <p className="orig">Currently: {b.original}</p>}
              <p style={{ margin: 0 }}>{b.tailored}</p>
              {b.why && <p className="why">Why: {b.why}</p>}
            </div>
          ))
        )}
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
