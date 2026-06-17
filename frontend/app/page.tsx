"use client";

import { useState } from "react";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export default function Home() {
  const [text, setText] = useState("");
  const [model, setModel] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function pingAgent() {
    setLoading(true);
    setError("");
    setText("");
    setModel("");
    try {
      const res = await fetch(`${BACKEND_URL}/agent/ping`);
      if (!res.ok) {
        throw new Error(`Backend responded with ${res.status}`);
      }
      const data: { model: string; text: string } = await res.json();
      setModel(data.model);
      setText(data.text);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main
      style={{
        maxWidth: 640,
        margin: "0 auto",
        padding: "4rem 1.5rem",
      }}
    >
      <h1 style={{ fontSize: "2.25rem", marginBottom: "0.5rem" }}>JobOps</h1>
      <p style={{ color: "#9fb0d0", marginTop: 0 }}>
        Multi-tenant agentic job-search assistant — M0 skeleton. The button
        below calls the FastAPI backend, which makes a live Anthropic call.
      </p>

      <button
        onClick={pingAgent}
        disabled={loading}
        style={{
          marginTop: "1.5rem",
          padding: "0.7rem 1.25rem",
          fontSize: "1rem",
          borderRadius: 8,
          border: "none",
          cursor: loading ? "default" : "pointer",
          background: loading ? "#34406b" : "#4f7cff",
          color: "white",
        }}
      >
        {loading ? "Pinging agent…" : "Ping the agent"}
      </button>

      {model && (
        <p style={{ marginTop: "1.5rem" }}>
          <strong>Model:</strong> <code>{model}</code>
        </p>
      )}

      {text && (
        <blockquote
          style={{
            borderLeft: "3px solid #4f7cff",
            margin: "0.5rem 0",
            padding: "0.5rem 1rem",
            background: "#121a33",
            borderRadius: 6,
          }}
        >
          {text}
        </blockquote>
      )}

      {error && (
        <p style={{ marginTop: "1.5rem", color: "#ff7676" }}>Error: {error}</p>
      )}
    </main>
  );
}
