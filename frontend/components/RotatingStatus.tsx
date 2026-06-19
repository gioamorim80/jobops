"use client";

import { useEffect, useState } from "react";

// Honest steps of the score+tailor run, with a couple of gentle "still working"
// lines so longer waits feel acknowledged. Loops continuously until the result
// arrives (the component unmounts) — never freezes on the last line.
const MESSAGES = [
  "Reading the posting…",
  "Sizing it up against your real experience…",
  "Finding your strongest honest angles…",
  "Tailoring your bullets — no embellishment…",
  "Good things take a moment…",
  "Still on it — almost there…",
];

const INTERVAL_MS = 3500;

export function RotatingStatus() {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const timer = setInterval(
      () => setIndex((i) => (i + 1) % MESSAGES.length),
      INTERVAL_MS,
    );
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="center-screen" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <span>{MESSAGES[index]}</span>
    </div>
  );
}
