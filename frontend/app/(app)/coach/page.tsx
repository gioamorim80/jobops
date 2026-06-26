"use client";

import {
  Fragment,
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";

import { ProposalCard } from "@/components/ProposalCard";
import { backendPost } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import type { ChatMessage, EnrichResponse } from "@/lib/types";

const WELCOME: ChatMessage = {
  role: "assistant",
  content:
    "Hi! I'm your coach. Think of me as the friend who remembers the impressive " +
    "thing you actually built and won't let you undersell it. Tell me about a " +
    "project you're proud of — or anything your resume didn't quite capture — and " +
    "we'll get the true parts into your profile. Where should we start?",
};

export default function CoachPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [limited, setLimited] = useState(false);
  const [error, setError] = useState("");
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
      if (data.status !== "ok") {
        // limit_reached or a backend error: show the message and let the user
        // retry. Only the daily limit disables further input.
        setMessages((m) => [
          ...m,
          { role: "assistant", content: data.message },
        ]);
        if (data.status === "limit_reached") setLimited(true);
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
        A warm place to add the true context your resume missed — stories of
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
                onDismiss={() => dismissProposal(i)}
                onError={setError}
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
