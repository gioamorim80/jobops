"use client";

import { useEffect, useState } from "react";

// Honest steps of the score+tailor run. Advances in order ~every 2.5s and
// stops on the last line while the request is still in flight.
const MESSAGES = [
  "Reading the posting…",
  "Sizing it up against your real experience…",
  "Finding your strongest honest angles…",
  "Tailoring your bullets — no embellishment…",
  "Almost there…",
];

const INTERVAL_MS = 2500;

export function RotatingStatus() {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (index >= MESSAGES.length - 1) return;
    const timer = setTimeout(() => setIndex((i) => i + 1), INTERVAL_MS);
    return () => clearTimeout(timer);
  }, [index]);

  return (
    <div className="center-screen" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <span>{MESSAGES[index]}</span>
    </div>
  );
}
