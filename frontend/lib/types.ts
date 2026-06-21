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

export type AlertFrequency = "off" | "daily" | "weekly";

export interface Preferences {
  user_id: string;
  alert_frequency: AlertFrequency;
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
      tailor: TailorResult;
    }
  | { status: "unreadable" | "limit_reached" | "no_profile"; message: string };

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

// A saved tailoring row (read via RLS — only ever the user's own).
export interface Tailoring {
  id: string;
  source_url: string | null;
  job_text: string | null;
  score: ScoreResult | null;
  tailored_bullets: TailoredBullet[] | null;
  analysis: string | null;
  approved: boolean;
  applied_at: string | null;
  created_at: string;
}
