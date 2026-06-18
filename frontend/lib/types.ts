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
