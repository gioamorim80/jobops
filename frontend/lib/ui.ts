import type { Decision } from "./types";

export const decisionClass: Record<Decision, string> = {
  APPLY: "decision decision-apply",
  STRETCH: "decision decision-stretch",
  SKIP: "decision decision-skip",
};

// First meaningful line / snippet of a posting, for history list labels.
export function jobSnippet(
  jobText: string | null,
  sourceUrl: string | null,
  max = 90,
): string {
  const text = (jobText ?? "").trim();
  if (text) {
    const firstLine = text.split("\n").find((l) => l.trim().length > 0) ?? text;
    const clean = firstLine.trim();
    return clean.length > max ? `${clean.slice(0, max)}…` : clean;
  }
  if (sourceUrl) {
    try {
      return new URL(sourceUrl).hostname.replace(/^www\./, "");
    } catch {
      return sourceUrl;
    }
  }
  return "Scored job";
}
