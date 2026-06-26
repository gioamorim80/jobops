import type { Decision } from "./types";

export const decisionClass: Record<Decision, string> = {
  APPLY: "decision decision-apply",
  STRETCH: "decision decision-stretch",
  SKIP: "decision decision-skip",
};

// Qualitative band for the 0–100 fit score, so small run-to-run variance reads
// as the same verdict rather than an inconsistency. Describes fit quality only —
// it deliberately avoids the word "Stretch" so it never collides with the
// separate STRETCH decision label. Cutoffs MUST stay identical to the backend
// matcher.score_band so a stored band and a client-derived one never disagree.
// LABELS ONLY: calibrated against the early score distribution (max observed ~78);
// revisit as more data accumulates.
export function fitBand(fit: number): string {
  if (fit >= 74) return "Strong fit";
  if (fit >= 62) return "Solid fit";
  if (fit >= 48) return "Moderate fit";
  return "Likely skip";
}

// Label for a scored-job history row: the role and company the scorer extracted
// from the posting. Shows "Role — Company" when both are known, just the role
// when the company couldn't be determined, and a short sensible fallback (the
// posting's host, else a generic label) when neither is set — never raw
// description copy. Rows scored before role/company existed fall back too.
export function jobLabel(
  role: string | null,
  company: string | null,
  sourceUrl: string | null,
): string {
  const r = (role ?? "").trim();
  const c = (company ?? "").trim();
  if (r && c) return `${r} — ${c}`;
  if (r) return r;
  if (sourceUrl) {
    try {
      return new URL(sourceUrl).hostname.replace(/^www\./, "");
    } catch {
      /* fall through to the generic label */
    }
  }
  return "Scored job";
}
