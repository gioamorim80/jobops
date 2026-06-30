"use client";

import { Fragment, useState, type KeyboardEvent } from "react";

import { ProposalCard } from "@/components/ProposalCard";
import { backendPost } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import type {
  ChatMessage,
  EnrichResponse,
  ScoreResponse,
  ScoreResult,
  TailorResponse,
  TailoredBullet,
} from "@/lib/types";
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

// Render of a saved tailoring (history detail), as a client component so it can
// carry the same interactive blocks the live /score page has: the on-demand
// Tailor button and the "Something's missing?" coach block. score/bullets/
// analysis/approved are seeded from the saved row and held in state, so an
// on-demand tailor or a post-apply re-score updates the view in place. The job
// reference is used here too: id for the id-only tailor call, and source_url/
// job_text to force a re-score through /ondemand/score after the user confirms a
// profile update. (role/company are passed through but not displayed yet.) The
// editable tailor variant still lives in the /score page; this view is read-only
// apart from these two actions.
export function ScoredResult({
  id,
  source_url,
  job_text,
  score: initialScore,
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
  // Local state seeded from the saved row. Tailoring on demand, and the re-score
  // that follows a confirmed profile update, both write back here so the view
  // updates in place without a reload.
  const [score, setScore] = useState<ScoreResult>(initialScore);
  const [bullets, setBullets] = useState<TailoredBullet[]>(initialBullets);
  const [analysis, setAnalysis] = useState(initialAnalysis);
  const [approved, setApproved] = useState(initialApproved);
  const [tailoring, setTailoring] = useState(false);
  // Latched true only on a cap (limit_reached) response, so the button can't be
  // clicked into the cap again. Not set by no_profile or network errors.
  const [tailorCapped, setTailorCapped] = useState(false);
  // Shared feedback, rendered once near the top: notice (info, e.g. a cap),
  // error (problems), and the post-re-score success banner.
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [rescored, setRescored] = useState(false);

  // "Something's missing?" coach thread — a lightweight running exchange that
  // reuses the profile-enrichment flow. The job text is never sent to /enrich;
  // the profile is injected server-side. Profile writes happen only through
  // ProposalCard -> /enrich/apply (the shared confirm gate).
  const [enrichThread, setEnrichThread] = useState<ChatMessage[]>([]);
  const [enrichInput, setEnrichInput] = useState("");
  const [enrichSending, setEnrichSending] = useState(false);
  const [enrichLimited, setEnrichLimited] = useState(false);

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
    setRescored(false);
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

  // Send the user's added context (and any follow-up replies) to the enrichment
  // coach. We post the running thread so the coach can revise across turns. The
  // job text is never sent here — enrichment describes profile-level true
  // experience, not this posting.
  async function sendEnrich() {
    const content = enrichInput.trim();
    if (!content || enrichSending) return;
    setError("");
    const next: ChatMessage[] = [...enrichThread, { role: "user", content }];
    setEnrichThread(next);
    setEnrichInput("");
    setEnrichSending(true);
    try {
      const data = await backendPost<EnrichResponse>(
        "/enrich/chat",
        await token(),
        { messages: next.map((m) => ({ role: m.role, content: m.content })) },
      );
      if (data.status !== "ok") {
        // limit_reached or a backend error: show the coach's message in-thread
        // and let the user try again. Only the daily limit disables further input.
        setEnrichThread((t) => [
          ...t,
          { role: "assistant", content: data.message },
        ]);
        if (data.status === "limit_reached") setEnrichLimited(true);
      } else {
        setEnrichThread((t) => [
          ...t,
          { role: "assistant", content: data.reply, proposal: data.proposal },
        ]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setEnrichSending(false);
    }
  }

  function dismissEnrichProposal(index: number) {
    setEnrichThread((t) =>
      t.map((msg, i) => (i === index ? { ...msg, proposal: null } : msg)),
    );
  }

  // Fires only after ProposalCard confirms a profile change via /enrich/apply.
  // The profile changed, so this job's saved score is stale: re-score it against
  // the updated profile. There's no id-based score endpoint, so we re-send the
  // saved job reference through the existing force path — source_url (when set)
  // keys the cache so the SAME row is overwritten, and job_text is sent as the
  // body so we never re-fetch the posting. One of the two is always set; if
  // somehow neither is, we keep the saved profile change and tell the user the
  // score will refresh next time. We mark the proposal applied and drop its card
  // first so it can't be re-applied.
  async function handleEnrichApplied(index: number) {
    setEnrichThread((t) =>
      t.map((msg, i) =>
        i === index ? { ...msg, applied: true, proposal: null } : msg,
      ),
    );
    setError("");
    setNotice("");
    setRescored(false);

    if (!source_url && !job_text) {
      setNotice(
        "Saved to your profile. We'll refresh this job's score the next time it's scored.",
      );
      return;
    }

    try {
      const data = await backendPost<ScoreResponse>(
        "/ondemand/score",
        await token(),
        {
          url: source_url ?? undefined,
          text: job_text ?? undefined,
          force: true,
        },
      );
      if (data.status !== "ok") {
        // Cap -> info notice; anything else -> error. The profile change still
        // stands either way (ProposalCard saved it before calling us).
        if (data.status === "limit_reached") {
          setNotice(data.message);
        } else {
          setError(data.message);
        }
        return;
      }
      setScore(data.score);
      setBullets(data.tailor ? data.tailor.tailored_bullets : []);
      setAnalysis(data.tailor ? data.tailor.analysis : "");
      setApproved(data.approved);
      setRescored(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  function onEnrichKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendEnrich();
    }
  }

  return (
    <>
      {rescored && (
        <div
          className="alert alert-success"
          style={{ marginBottom: "1.25rem" }}
        >
          Re-scored with your updated profile.
        </div>
      )}
      {notice && (
        <div className="alert alert-info" style={{ marginBottom: "1.25rem" }}>
          {notice}
        </div>
      )}
      {error && (
        <div className="alert alert-error" style={{ marginBottom: "1.25rem" }}>
          {error}
        </div>
      )}

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
        <div className="card-title">Something&apos;s missing?</div>
        <p className="hint" style={{ marginTop: 0, marginBottom: "1rem" }}>
          Marked something as a gap that you actually have? Add the context and
          we&apos;ll update your profile — nothing saves until you confirm. Once
          you confirm, we update your profile and re-score this job for you
          automatically.
        </p>

        {enrichThread.map((m, i) => (
          <Fragment key={i}>
            <div
              className={
                m.role === "user" ? "bubble bubble-user" : "bubble bubble-agent"
              }
            >
              {m.content}
            </div>
            {m.role === "assistant" && m.proposal && (
              <ProposalCard
                proposal={m.proposal}
                onApplied={() => handleEnrichApplied(i)}
                onDismiss={() => dismissEnrichProposal(i)}
                onError={setError}
              />
            )}
            {m.role === "assistant" && m.applied && (
              <p className="proposal-saved">Saved to your profile.</p>
            )}
          </Fragment>
        ))}

        {enrichSending && (
          <div className="bubble bubble-agent typing">
            <span className="spinner" aria-hidden="true" /> thinking…
          </div>
        )}

        {enrichLimited ? (
          <div className="alert alert-info" style={{ marginTop: "1rem" }}>
            You&apos;ve reached today&apos;s coaching limit. We&apos;ll be right
            here tomorrow.
          </div>
        ) : (
          <div
            className="chat-input"
            style={{ marginTop: enrichThread.length ? "1rem" : 0 }}
          >
            <textarea
              className="textarea"
              value={enrichInput}
              onChange={(e) => setEnrichInput(e.target.value)}
              onKeyDown={onEnrichKeyDown}
              placeholder={
                enrichThread.length
                  ? "Reply to refine it…"
                  : "e.g. I actually led the Kubernetes migration — it just wasn't on my resume."
              }
              rows={2}
              maxLength={2000}
              disabled={enrichSending}
              aria-label="Add context for your profile"
            />
            <button
              type="button"
              className="btn"
              onClick={sendEnrich}
              disabled={enrichSending || !enrichInput.trim()}
            >
              {enrichThread.length ? "Send" : "Suggest a profile update"}
            </button>
          </div>
        )}
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
