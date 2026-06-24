export interface ParsedProfile {
  skills: string[];
  target_roles: string[];
  seniority: string;
  domains: string[];
  locations: string[];
  remote_pref: string;
  comp_floor: string;
  attribution_notes: string[];
}

export interface Profile {
  user_id: string;
  full_name: string | null;
  email: string | null;
  resume_file_path: string | null;
  parsed: ParsedProfile | null;
  onboarding_complete: boolean;
}

export interface Preferences {
  user_id: string;
  email_opt_in: boolean;
  score_threshold: number;
}

export interface Draft {
  full_name: string;
  email: string;
  skills: string[];
  roles_held: string[];
  seniority: string;
  domains: string[];
  locations: string[];
  summary: string;
}

export type Decision = "APPLY" | "STRETCH" | "SKIP";

export interface ScoreResult {
  fit: number;
  decision: Decision;
  cleared: string[];
  gaps: string[];
  referral_angle: string;
  pitch: string;
}

export interface TailoredBullet {
  original: string;
  tailored: string;
  why: string;
  where?: string; // which role/section of the resume this edit applies under
}

export interface TailorResult {
  tailored_bullets: TailoredBullet[];
  analysis: string;
  flags: string[];
}

export type ScoreResponse =
  | {
      status: "ok";
      id: string;
      cached: boolean;
      approved: boolean;
      score: ScoreResult;
      tailored: boolean; // whether this job already has saved tailoring
      tailor: TailorResult | null; // saved tailoring, or null if not tailored yet
    }
  | { status: "unreadable" | "limit_reached" | "no_profile"; message: string };

// The on-demand tailoring step (the expensive Sonnet step), run only on click.
export type TailorResponse =
  | { status: "ok"; id: string; approved: boolean; tailor: TailorResult }
  | { status: "limit_reached" | "no_profile"; message: string };

export interface ProposalChanges {
  add_skills: string[];
  add_domains: string[];
  add_target_roles: string[];
  add_attribution_notes: string[];
  set_seniority: string;
  set_remote_pref: string;
}

export interface Proposal {
  summary: string;
  changes: ProposalChanges;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  proposal?: Proposal | null;
  applied?: boolean;
}

export type EnrichResponse =
  | { status: "ok"; reply: string; proposal: Proposal | null }
  | { status: "limit_reached" | "error"; message: string };

// A per-user automated match (read via RLS — only ever the user's own), with the
// shared job it points at embedded from the jobs pool.
export interface Match {
  id: string;
  score: number | null;
  band: string | null;
  decision: Decision | null;
  cleared: string[] | null;
  gaps: string[] | null;
  analysis: string | null;
  posted_at: string | null;
  jobs: {
    title: string | null;
    company: string | null;
    location_display: string | null;
    source_url: string | null;
  } | null;
}

// The minimal context the score page's ?match=<id> tailor flow needs, returned by
// POST /matches/context (JWT-scoped to the caller's own match). No score/analysis —
// that flow re-scores the user-pasted full JD.
export interface MatchContext {
  id: string;
  title: string | null;
  company: string | null;
  source_url: string | null;
}

// A saved tailoring row (read via RLS — only ever the user's own).
export interface Tailoring {
  id: string;
  source_url: string | null;
  job_text: string | null;
  role: string | null;
  company: string | null;
  score: ScoreResult | null;
  tailored_bullets: TailoredBullet[] | null;
  analysis: string | null;
  approved: boolean;
  applied_at: string | null;
  created_at: string;
}
