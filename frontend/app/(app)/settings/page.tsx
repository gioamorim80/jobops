"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { backendPost } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import type { AlertFrequency, ParsedProfile } from "@/lib/types";

type Load = "loading" | "ready" | "error";

const toList = (value: string): string[] =>
  value
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

const fromList = (items: string[] | undefined): string =>
  (items ?? []).join(", ");

export default function SettingsPage() {
  const [load, setLoad] = useState<Load>("loading");
  const [loadError, setLoadError] = useState("");

  // profile fields
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [targetRoles, setTargetRoles] = useState("");
  const [seniority, setSeniority] = useState("");
  const [skills, setSkills] = useState("");
  const [domains, setDomains] = useState("");
  const [locations, setLocations] = useState("");
  const [remotePref, setRemotePref] = useState("flexible");

  // preferences
  const [frequency, setFrequency] = useState<AlertFrequency>("weekly");
  const [threshold, setThreshold] = useState(60);

  // Note: comp_floor and attribution_notes are intentionally not held or sent.
  // The backend preserves them server-side from the live row, so we never risk
  // wiping coach-written attribution_notes with stale client state.

  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const supabase = createClient();
    (async () => {
      const {
        data: { user },
      } = await supabase.auth.getUser();
      if (!user) {
        setLoad("error");
        setLoadError("Your session expired. Please sign in again.");
        return;
      }

      // RLS scopes both reads to the current user's own rows only.
      const [{ data: profile }, { data: prefs, error: prefsError }] =
        await Promise.all([
          supabase
            .from("profiles")
            .select("full_name, email, parsed")
            .eq("user_id", user.id)
            .maybeSingle(),
          supabase
            .from("preferences")
            .select("alert_frequency, score_threshold")
            .eq("user_id", user.id)
            .maybeSingle(),
        ]);

      if (prefsError) {
        setLoad("error");
        setLoadError(prefsError.message);
        return;
      }

      const parsed = (profile?.parsed ?? {}) as Partial<ParsedProfile>;
      setFullName(profile?.full_name ?? "");
      setEmail(profile?.email ?? user.email ?? "");
      setTargetRoles(fromList(parsed.target_roles));
      setSeniority(parsed.seniority ?? "");
      setSkills(fromList(parsed.skills));
      setDomains(fromList(parsed.domains));
      setLocations(fromList(parsed.locations));
      setRemotePref(parsed.remote_pref || "flexible");

      if (prefs) {
        setFrequency(prefs.alert_frequency as AlertFrequency);
        setThreshold(prefs.score_threshold);
      }
      setLoad("ready");
    })();
  }, []);

  async function save() {
    setSaving(true);
    setSaved(false);
    setError("");
    try {
      const supabase = createClient();
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session)
        throw new Error("Your session expired. Please sign in again.");

      await backendPost("/onboarding/profile", session.access_token, {
        full_name: fullName,
        email,
        parsed: {
          skills: toList(skills),
          target_roles: toList(targetRoles),
          seniority,
          domains: toList(domains),
          locations: toList(locations),
          remote_pref: remotePref,
        },
        preferences: { alert_frequency: frequency, score_threshold: threshold },
      });
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setSaving(false);
    }
  }

  if (load === "loading") {
    return (
      <div className="center-screen">
        <span className="spinner" />
        Loading your profile…
      </div>
    );
  }

  if (load === "error") {
    return (
      <div style={{ maxWidth: 560 }}>
        <h1>Profile &amp; settings</h1>
        <div className="alert alert-error">{loadError}</div>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 640 }}>
      <div className="section-head">
        <div>
          <h1 style={{ marginBottom: "0.25rem" }}>Profile &amp; settings</h1>
          <p className="muted" style={{ margin: 0 }}>
            Edit your details directly — no need to re-upload your resume.
          </p>
        </div>
        <Link href="/onboarding" className="btn btn-ghost btn-sm">
          Replace resume
        </Link>
      </div>

      <div className="card">
        <div className="card-title">Profile</div>

        <div className="row">
          <div className="field">
            <label className="label" htmlFor="fullName">
              Full name
            </label>
            <input
              id="fullName"
              className="input"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
          </div>
          <div className="field">
            <label className="label" htmlFor="email">
              Email for alerts
            </label>
            <input
              id="email"
              className="input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
        </div>

        <div className="field">
          <label className="label" htmlFor="targetRoles">
            Target roles
          </label>
          <input
            id="targetRoles"
            className="input"
            value={targetRoles}
            onChange={(e) => setTargetRoles(e.target.value)}
            placeholder="Comma-separated, e.g. Senior Backend Engineer"
          />
        </div>

        <div className="row">
          <div className="field">
            <label className="label" htmlFor="seniority">
              Seniority
            </label>
            <input
              id="seniority"
              className="input"
              value={seniority}
              onChange={(e) => setSeniority(e.target.value)}
              placeholder="e.g. senior"
            />
          </div>
          <div className="field">
            <label className="label" htmlFor="remotePref">
              Remote preference
            </label>
            <select
              id="remotePref"
              className="select"
              value={remotePref}
              onChange={(e) => setRemotePref(e.target.value)}
            >
              <option value="remote">Remote only</option>
              <option value="hybrid">Hybrid</option>
              <option value="onsite">Onsite</option>
              <option value="flexible">Flexible</option>
            </select>
          </div>
        </div>

        <div className="field">
          <label className="label" htmlFor="locations">
            Locations
          </label>
          <input
            id="locations"
            className="input"
            value={locations}
            onChange={(e) => setLocations(e.target.value)}
            placeholder="Comma-separated, e.g. Lisbon, Remote (EU)"
          />
        </div>

        <div className="field">
          <label className="label" htmlFor="skills">
            Skills
          </label>
          <textarea
            id="skills"
            className="textarea"
            value={skills}
            onChange={(e) => setSkills(e.target.value)}
            placeholder="Comma-separated"
          />
        </div>

        <div className="field" style={{ marginBottom: 0 }}>
          <label className="label" htmlFor="domains">
            Domains
          </label>
          <input
            id="domains"
            className="input"
            value={domains}
            onChange={(e) => setDomains(e.target.value)}
            placeholder="e.g. fintech, healthcare"
          />
        </div>
      </div>

      <div className="card">
        <div className="card-title">Alerts</div>

        <div className="field">
          <label className="label" htmlFor="frequency">
            Alert frequency
          </label>
          <select
            id="frequency"
            className="select"
            value={frequency}
            onChange={(e) => setFrequency(e.target.value as AlertFrequency)}
          >
            <option value="off">Off — no emails</option>
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
          </select>
          <p className="hint">How often we email you new scored matches.</p>
        </div>

        <div className="field" style={{ marginBottom: 0 }}>
          <label className="label" htmlFor="threshold">
            Score threshold — {threshold}
          </label>
          <input
            id="threshold"
            className="input"
            type="range"
            min={0}
            max={100}
            step={5}
            value={threshold}
            onChange={(e) => setThreshold(Number(e.target.value))}
          />
          <p className="hint">
            Only surface matches scoring at or above this fit score (default
            60).
          </p>
        </div>
      </div>

      {error && (
        <div className="alert alert-error" style={{ marginBottom: "1rem" }}>
          {error}
        </div>
      )}
      {saved && (
        <div className="alert alert-success" style={{ marginBottom: "1rem" }}>
          Saved.
        </div>
      )}

      <button type="button" className="btn" onClick={save} disabled={saving}>
        {saving ? (
          <>
            <span className="spinner" /> Saving…
          </>
        ) : (
          "Save changes"
        )}
      </button>
    </div>
  );
}
