"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { RotatingStatus } from "@/components/RotatingStatus";
import { backendPost } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import type {
  ScoreResponse,
  ScoreResult,
  TailorResponse,
  TailorResult,
} from "@/lib/types";
import { decisionClass, fitBand } from "@/lib/ui";

type Phase = "input" | "loading" | "result";

function List({ items, empty }: { items: string[]; empty: string }) {
  if (!items.length) return <p className="faint">{empty}</p>;
  return (
    <ul className="list-clean">
      {items.map((item, i) => (
        <li key={i}>{item}</li>
      ))}
    </ul>
  );
}

export default function ScorePage() {
  const [phase, setPhase] = useState<Phase>("input");
  const [url, setUrl] = useState("");
  const [text, setText] = useState("");

  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [id, setId] = useState<string | null>(null);
  const [score, setScore] = useState<ScoreResult | null>(null);
  const [tailor, setTailor] = useState<TailorResult | null>(null);
  const [bullets, setBullets] = useState<string[]>([]);
  const [cached, setCached] = useState(false);

  const [tailoring, setTailoring] = useState(false);
  const [approving, setApproving] = useState(false);
  const [approved, setApproved] = useState(false);

  // A Match's "Tailor my resume for this" deep-links here as ?url=…; prefill and
  // score it right away so the user lands on the result + on-demand tailor step.
  useEffect(() => {
    const deepLink = new URLSearchParams(window.location.search).get("url");
    if (deepLink) {
      setUrl(deepLink);
      void run(false, deepLink);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function token(): Promise<string> {
    const supabase = createClient();
    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (!session)
      throw new Error("Your session expired. Please sign in again.");
    return session.access_token;
  }

  async function run(force = false, overrideUrl?: string) {
    setError("");
    setNotice("");
    const urlValue = (overrideUrl ?? url).trim();
    if (!urlValue && !text.trim()) {
      setError("Paste a job link or the posting text to score it.");
      return;
    }
    setPhase("loading");
    try {
      const data = await backendPost<ScoreResponse>(
        "/ondemand/score",
        await token(),
        {
          url: urlValue || null,
          text: text.trim() || null,
          force,
        },
      );

      if (data.status !== "ok") {
        setNotice(data.message);
        setPhase("input");
        return;
      }

      setId(data.id);
      setScore(data.score);
      setTailor(data.tailor);
      setBullets(
        data.tailor ? data.tailor.tailored_bullets.map((b) => b.tailored) : [],
      );
      setCached(data.cached);
      setApproved(data.approved);
      setPhase("result");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
      setPhase("input");
    }
  }

  async function approve() {
    if (!id || !tailor) return;
    setApproving(true);
    setError("");
    try {
      const edited = tailor.tailored_bullets.map((b, i) => ({
        ...b,
        tailored: bullets[i] ?? b.tailored,
      }));
      await backendPost("/ondemand/approve", await token(), {
        id,
        tailored_bullets: edited,
        analysis: tailor.analysis,
      });
      setApproved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setApproving(false);
    }
  }

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
        setNotice(data.message);
        return;
      }
      setTailor(data.tailor);
      setBullets(data.tailor.tailored_bullets.map((b) => b.tailored));
      setApproved(data.approved);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setTailoring(false);
    }
  }

  function reset() {
    setPhase("input");
    setUrl("");
    setText("");
    setId(null);
    setScore(null);
    setTailor(null);
    setBullets([]);
    setCached(false);
    setTailoring(false);
    setApproved(false);
    setError("");
    setNotice("");
  }

  if (phase === "loading") {
    return <RotatingStatus />;
  }

  if (phase === "result" && score) {
    return (
      <div style={{ maxWidth: 720 }}>
        <div className="section-head">
          <h1 style={{ margin: 0 }}>Your fit</h1>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={reset}
          >
            Score another
          </button>
        </div>

        {cached && (
          <div className="alert alert-info" style={{ marginBottom: "1.25rem" }}>
            Showing your saved result for this job — no new analysis was run. If
            your profile or the posting changed,{" "}
            <button
              type="button"
              className="linklike"
              onClick={() => run(true)}
            >
              re-score it
            </button>
            .
          </div>
        )}

        <div className="card">
          <div className="score-head">
            <span className="score-num">
              {score.fit}
              <small>/100</small>
            </span>
            <span className="band">{fitBand(score.fit)}</span>
            <span className={decisionClass[score.decision]}>
              {score.decision}
            </span>
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

        {notice && (
          <div className="alert alert-info" style={{ marginTop: "1.25rem" }}>
            {notice}
          </div>
        )}
        {error && (
          <div className="alert alert-error" style={{ marginTop: "1.25rem" }}>
            {error}
          </div>
        )}

        {!tailor ? (
          <div className="card">
            <div className="card-title">Tailor your resume for this</div>
            <p className="hint" style={{ marginTop: 0, marginBottom: "1rem" }}>
              Scoring is done. When you want to apply, generate suggested resume
              changes from your real experience — reordered and rephrased, never
              invented. This is the deeper step, so run it only for jobs you mean
              to pursue.
            </p>
            <button
              type="button"
              className="btn"
              onClick={tailorResume}
              disabled={tailoring}
            >
              {tailoring ? (
                <>
                  <span className="spinner" /> Tailoring…
                </>
              ) : (
                "Tailor my resume for this"
              )}
            </button>
          </div>
        ) : (
          <>
            {tailor.flags.length > 0 && (
              <div className="card">
                <div className="card-title">Please review</div>
                <div className="flags">
                  {tailor.flags.map((flag, i) => (
                    <span key={i} className="alert alert-info">
                      {flag}
                    </span>
                  ))}
                </div>
                <p className="hint" style={{ marginTop: "0.75rem" }}>
                  We never invent metrics or claims. Anything flagged needs your
                  real number or a correction before you use it.
                </p>
              </div>
            )}

            <div className="card">
              <div className="card-title">Suggested changes to your resume</div>
              <p
                className="hint"
                style={{ marginTop: 0, marginBottom: "1rem" }}
              >
                Each one shows where on your resume it applies. Reordered and
                rephrased from your real experience — never invented. Edit any
                of them, then approve.
              </p>
              {tailor.tailored_bullets.length === 0 && (
                <p className="faint">No suggestions were generated.</p>
              )}
              {tailor.tailored_bullets.map((b, i) => (
                <div key={i} className="bullet">
                  {b.where && <p className="where">{b.where}</p>}
                  {b.original && <p className="orig">Currently: {b.original}</p>}
                  <textarea
                    className="textarea"
                    value={bullets[i] ?? ""}
                    onChange={(e) => {
                      const next = [...bullets];
                      next[i] = e.target.value;
                      setBullets(next);
                    }}
                    disabled={approved}
                  />
                  {b.why && <p className="why">Why: {b.why}</p>}
                </div>
              ))}
            </div>

            {tailor.analysis && (
              <div className="card">
                <div className="card-title">Match analysis</div>
                <p className="muted" style={{ margin: 0 }}>
                  {tailor.analysis}
                </p>
              </div>
            )}

            {approved ? (
              <div
                className="alert alert-success"
                style={{ marginTop: "1rem" }}
              >
                Approved and saved. Nothing is sent anywhere on your behalf —
                these are yours to use.
              </div>
            ) : (
              <div style={{ marginTop: "1.25rem" }}>
                <button
                  type="button"
                  className="btn"
                  onClick={approve}
                  disabled={approving}
                >
                  {approving ? (
                    <>
                      <span className="spinner" /> Saving…
                    </>
                  ) : (
                    "Approve these bullets"
                  )}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    );
  }

  // input phase
  return (
    <div style={{ maxWidth: 640 }}>
      <h1>Score a job</h1>
      <p className="muted">
        Paste a job link or the posting text for an honest fit score, grounded
        only in what&apos;s true on your profile. Tailoring your resume is a
        separate step you choose, on the jobs you want to pursue.
      </p>

      <div className="card">
        <div className="field">
          <label className="label" htmlFor="url">
            Job link
          </label>
          <input
            id="url"
            className="input"
            type="url"
            inputMode="url"
            placeholder="https://…"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />
          <p className="hint">
            Some sites block fetching — if a link won&apos;t read, paste the
            text below instead.
          </p>
        </div>

        <div className="field" style={{ marginBottom: 0 }}>
          <label className="label" htmlFor="text">
            …or paste the job description
          </label>
          <textarea
            id="text"
            className="textarea"
            style={{ minHeight: 160 }}
            placeholder="Paste the full posting text here"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </div>
      </div>

      {notice && (
        <div className="alert alert-info" style={{ marginBottom: "1rem" }}>
          {notice}
          {notice.toLowerCase().includes("profile") && (
            <>
              {" "}
              <Link href="/onboarding">Set up your profile</Link>.
            </>
          )}
        </div>
      )}
      {error && (
        <div className="alert alert-error" style={{ marginBottom: "1rem" }}>
          {error}
        </div>
      )}

      <button type="button" className="btn" onClick={() => run(false)}>
        Score
      </button>
    </div>
  );
}
