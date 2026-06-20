"use client";

import {
  Fragment,
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";

import { backendPost } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import type { ChatMessage, EnrichResponse, Proposal } from "@/lib/types";

const WELCOME: ChatMessage = {
  role: "assistant",
  content:
    "Oi! I'm your coach. Think of me as the friend who remembers the impressive " +
    "thing you actually built and won't let you undersell it. Tell me about a " +
    "project you're proud of — or anything your résumé didn't quite capture — and " +
    "we'll get the true parts into your profile. Where should we start?",
};

function changeLines(c: Proposal["changes"]): string[] {
  const lines: string[] = [];
  if (c.add_skills.length) lines.push(`Add skills: ${c.add_skills.join(", ")}`);
  if (c.add_domains.length)
    lines.push(`Add domains: ${c.add_domains.join(", ")}`);
  if (c.add_target_roles.length)
    lines.push(`Add target roles: ${c.add_target_roles.join(", ")}`);
  if (c.add_attribution_notes.length)
    lines.push(`Attribution note: ${c.add_attribution_notes.join(" · ")}`);
  if (c.set_seniority) lines.push(`Set seniority: ${c.set_seniority}`);
  if (c.set_remote_pref)
    lines.push(`Set remote preference: ${c.set_remote_pref}`);
  return lines;
}

function ProposalCard({
  proposal,
  applied,
  applying,
  onConfirm,
  onDismiss,
}: {
  proposal: Proposal;
  applied: boolean;
  applying: boolean;
  onConfirm: () => void;
  onDismiss: () => void;
}) {
  return (
    <div className="proposal">
      <div className="proposal-title">Proposed update</div>
      {proposal.summary && (
        <p className="muted" style={{ margin: "0 0 0.6rem" }}>
          {proposal.summary}
        </p>
      )}
      <ul className="list-clean">
        {changeLines(proposal.changes).map((line, i) => (
          <li key={i}>{line}</li>
        ))}
      </ul>
      {applied ? (
        <p className="proposal-saved">Saved to your profile.</p>
      ) : (
        <div className="proposal-actions">
          <button
            type="button"
            className="btn btn-sm"
            onClick={onConfirm}
            disabled={applying}
          >
            {applying ? "Saving…" : "Add to profile"}
          </button>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={onDismiss}
            disabled={applying}
          >
            Not now
          </button>
        </div>
      )}
    </div>
  );
}

export default function CoachPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [limited, setLimited] = useState(false);
  const [error, setError] = useState("");
  const [applyingIndex, setApplyingIndex] = useState<number | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  async function token(): Promise<string> {
    const supabase = createClient();
    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (!session)
      throw new Error("Your session expired. Please sign in again.");
    return session.access_token;
  }

  async function send() {
    const text = input.trim();
    if (!text || sending) return;
    setError("");
    const next: ChatMessage[] = [...messages, { role: "user", content: text }];
    setMessages(next);
    setInput("");
    setSending(true);
    try {
      const payload = next.map((m) => ({ role: m.role, content: m.content }));
      const data = await backendPost<EnrichResponse>(
        "/enrich/chat",
        await token(),
        { messages: payload },
      );
      if (data.status === "limit_reached") {
        setMessages((m) => [
          ...m,
          { role: "assistant", content: data.message },
        ]);
        setLimited(true);
      } else {
        setMessages((m) => [
          ...m,
          { role: "assistant", content: data.reply, proposal: data.proposal },
        ]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setSending(false);
    }
  }

  async function confirmProposal(index: number) {
    const proposal = messages[index]?.proposal;
    if (!proposal) return;
    setApplyingIndex(index);
    setError("");
    try {
      await backendPost("/enrich/apply", await token(), {
        changes: proposal.changes,
      });
      setMessages((m) =>
        m.map((msg, i) => (i === index ? { ...msg, applied: true } : msg)),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setApplyingIndex(null);
    }
  }

  function dismissProposal(index: number) {
    setMessages((m) =>
      m.map((msg, i) => (i === index ? { ...msg, proposal: null } : msg)),
    );
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return (
    <div style={{ maxWidth: 720 }}>
      <h1>Coach</h1>
      <p className="muted">
        A warm place to add the true context your résumé missed — stories of
        what you built, who really owned what, the title the timeline flattened.
        We only save what you confirm.
      </p>

      <div className="chat-thread" role="log" aria-live="polite">
        {messages.map((m, i) => (
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
                applied={!!m.applied}
                applying={applyingIndex === i}
                onConfirm={() => confirmProposal(i)}
                onDismiss={() => dismissProposal(i)}
              />
            )}
          </Fragment>
        ))}
        {sending && (
          <div className="bubble bubble-agent typing">
            <span className="spinner" aria-hidden="true" /> thinking…
          </div>
        )}
        <div ref={endRef} />
      </div>

      {error && (
        <div className="alert alert-error" style={{ marginBottom: "1rem" }}>
          {error}
        </div>
      )}

      {limited ? (
        <div className="alert alert-info">
          We&apos;ll be right here tomorrow. Go enjoy your evening.
        </div>
      ) : (
        <div className="chat-input">
          <textarea
            className="textarea"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Tell me about something you built…"
            maxLength={2000}
            rows={2}
            disabled={sending}
            aria-label="Message the coach"
          />
          <button
            type="button"
            className="btn"
            onClick={send}
            disabled={sending || !input.trim()}
          >
            Send
          </button>
        </div>
      )}
    </div>
  );
}
