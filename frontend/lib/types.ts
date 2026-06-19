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

// A saved tailoring row (read via RLS — only ever the user's own).
export interface Tailoring {
  id: string;
  source_url: string | null;
  job_text: string | null;
  score: ScoreResult | null;
  tailored_bullets: TailoredBullet[] | null;
  analysis: string | null;
  approved: boolean;
  created_at: string;
}
