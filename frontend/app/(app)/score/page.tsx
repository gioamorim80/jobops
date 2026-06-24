"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { RotatingStatus } from "@/components/RotatingStatus";
import { backendPost } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import type {
  MatchContext,
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

  // ?match=<id> mode: tailor an already-found match by pasting its full JD. We load
  // only the match's role/company/link (JWT-scoped via /matches/context) for context;
  // the score+tailor runs on the pasted text, never by re-fetching the posting URL.
  const [matchId, setMatchId] = useState<string | null>(null);
  const [matchCtx, setMatchCtx] = useState<MatchContext | null>(null);
  const [matchError, setMatchError] = useState("");

  const [tailoring, setTailoring] = useState(false);
  // Latched true only after a cap (limit_reached) response from the tailor call,
  // so the Tailor button can't be clicked again. NOT set by generic/network errors
  // (those throw and land in catch) or by no_profile — only the cap response.
  const [tailorCapped, setTailorCapped] = useState(false);
  const [approving, setApproving] = useState(false);
  const [approved, setApproved] = useState(false);

  // Deep links. ?match=<id> opens the paste-the-full-JD tailor flow for a found
  // match (load context only, NO auto-fetch). The older ?url= path prefills and
  // auto-scores a pasted/fetched URL right away.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const matchParam = params.get("match");
    if (matchParam) {
      setMatchId(matchParam);
      void loadMatch(matchParam);
      return;
    }
    const deepLink = params.get("url");
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
        // A cap response (daily or monthly tailor cap) comes back as limit_reached.
        // Latch the button off so repeat clicks can't keep hitting the cap. Other
        // non-ok statuses (e.g. no_profile) leave the button clickable.
        if (data.status === "limit_reached") {
          setTailorCapped(true);
        }
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

  // Load the match context for ?match mode. JWT-scoped server-side: a match id that
  // isn't the caller's returns 404, so a user can't load another user's match here.
  async function loadMatch(id: string) {
    setPhase("loading");
    setError("");
    setNotice("");
    try {
      const ctx = await backendPost<MatchContext>(
        "/matches/context",
        await token(),
        { id },
      );
      setMatchCtx(ctx);
      setPhase("input");
    } catch {
      setMatchError(
        "We couldn't open this match. It may have been removed, or it isn't yours.",
      );
      setPhase("input");
    }
  }

  // ?match mode: one click scores the pasted full JD, then tailors it. Each step is a
  // normal capped call (/ondemand/score then /ondemand/tailor), and the score step's
  // exact-match cache still applies — the single button bypasses neither caps nor
  // cache, and never re-fetches the posting URL (it sends the pasted text).
  async function scoreAndTailor() {
    setError("");
    setNotice("");
    if (!text.trim()) {
      setError("Paste the full job description to score and tailor it.");
      return;
    }
    setPhase("loading");
    try {
      const accessToken = await token();
      const scoreData = await backendPost<ScoreResponse>(
        "/ondemand/score",
        accessToken,
        { url: null, text: text.trim(), force: false },
      );
      if (scoreData.status !== "ok") {
        setNotice(scoreData.message);
        setPhase("input");
        return;
      }
      setId(scoreData.id);
      setScore(scoreData.score);
      setCached(scoreData.cached);
      setApproved(scoreData.approved);
      // Exact-match cache can return an already-tailored job — show it and stop, no
      // second call.
      if (scoreData.tailor) {
        setTailor(scoreData.tailor);
        setBullets(scoreData.tailor.tailored_bullets.map((b) => b.tailored));
        setPhase("result");
        return;
      }
      // Tailor the just-scored row. A tailor-cap returns limit_reached: the score
      // still stands, and the result shows the (latched) Tailor button + the message.
      const tailorData = await backendPost<TailorResponse>(
        "/ondemand/tailor",
        accessToken,
        { id: scoreData.id },
      );
      setPhase("result");
      if (tailorData.status !== "ok") {
        setNotice(tailorData.message);
        if (tailorData.status === "limit_reached") setTailorCapped(true);
        return;
      }
      setTailor(tailorData.tailor);
      setBullets(tailorData.tailor.tailored_bullets.map((b) => b.tailored));
      setApproved(tailorData.approved);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
      setPhase("input");
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
    setTailorCapped(false);
    setApproved(false);
    setError("");
    setNotice("");
    // Leave ?match mode entirely: "Score another" returns to the normal score flow.
    setMatchId(null);
    setMatchCtx(null);
    setMatchError("");
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
              Decision: {score.decision}
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
              invented. This is the deeper step, so run it only for jobs you
              mean to pursue.
            </p>
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
                  {b.original && (
                    <p className="orig">Currently: {b.original}</p>
                  )}
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

  // ?match mode input: paste the full JD, then ONE combined "Score & tailor".
  if (matchId) {
    const matchLabel =
      [matchCtx?.title, matchCtx?.company].filter(Boolean).join(" — ") ||
      "this role";
    return (
      <div style={{ maxWidth: 640 }}>
        <h1>Tailor for this match</h1>
        {matchError ? (
          <div className="alert alert-error">{matchError}</div>
        ) : (
          <>
            <p className="muted">
              Job boards only give us a preview of each posting. To tailor
              accurately, open &ldquo;View posting,&rdquo; copy the full
              description, and paste it below.
            </p>

            <div className="card">
              <div className="card-title">
                Paste the full posting for {matchLabel}
              </div>
              {matchCtx?.source_url && (
                <p className="hint" style={{ marginTop: 0 }}>
                  <a
                    href={matchCtx.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="linklike"
                  >
                    View posting →
                  </a>
                </p>
              )}
              <div className="field" style={{ marginBottom: 0 }}>
                <label className="label" htmlFor="match-text">
                  Full job description
                </label>
                <textarea
                  id="match-text"
                  className="textarea"
                  style={{ minHeight: 200 }}
                  placeholder="Paste the full posting text here"
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                />
              </div>
            </div>

            {notice && (
              <div
                className="alert alert-info"
                style={{ marginBottom: "1rem" }}
              >
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
              <div
                className="alert alert-error"
                style={{ marginBottom: "1rem" }}
              >
                {error}
              </div>
            )}

            <button type="button" className="btn" onClick={scoreAndTailor}>
              Score &amp; tailor
            </button>
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
