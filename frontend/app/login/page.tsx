"use client";

import { useState, type FormEvent } from "react";

import { createClient } from "@/lib/supabase/client";

type State = "idle" | "sending" | "sent" | "error";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [state, setState] = useState<State>("idle");
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setState("sending");
    setError("");

    const supabase = createClient();
    const { error } = await supabase.auth.signInWithOtp({
      email: email.trim(),
      options: {
        emailRedirectTo: `${window.location.origin}/auth/callback`,
      },
    });

    if (error) {
      setError(error.message);
      setState("error");
    } else {
      setState("sent");
    }
  }

  return (
    <div className="container" style={{ maxWidth: 460, paddingTop: "6vh" }}>
      <div style={{ textAlign: "center", marginBottom: "1.5rem" }}>
        <h1 style={{ fontSize: "1.8rem" }}>Sign in to JobOps</h1>
        <p className="muted">
          We&apos;ll email you a magic link — no password.
        </p>
      </div>

      <div className="card">
        {state === "sent" ? (
          <div className="stack">
            <div className="alert alert-success">
              Check your inbox. We sent a sign-in link to{" "}
              <strong>{email}</strong>.
            </div>
            <button
              type="button"
              className="btn btn-ghost btn-block"
              onClick={() => setState("idle")}
            >
              Use a different email
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <div className="field">
              <label className="label" htmlFor="email">
                Email address
              </label>
              <input
                id="email"
                className="input"
                type="email"
                inputMode="email"
                autoComplete="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                disabled={state === "sending"}
              />
            </div>

            {state === "error" && (
              <div
                className="alert alert-error"
                style={{ marginBottom: "1rem" }}
              >
                {error}
              </div>
            )}

            <button
              type="submit"
              className="btn btn-block"
              disabled={state === "sending" || email.trim().length === 0}
            >
              {state === "sending" ? (
                <>
                  <span className="spinner" /> Sending…
                </>
              ) : (
                "Send magic link"
              )}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
