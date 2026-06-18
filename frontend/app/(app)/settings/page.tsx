"use client";

import { useEffect, useState } from "react";

import { createClient } from "@/lib/supabase/client";
import type { AlertFrequency } from "@/lib/types";

type Load = "loading" | "ready" | "error";

export default function SettingsPage() {
  const [load, setLoad] = useState<Load>("loading");
  const [frequency, setFrequency] = useState<AlertFrequency>("weekly");
  const [threshold, setThreshold] = useState(60);
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
        setError("Your session expired. Please sign in again.");
        return;
      }
      // RLS scopes this to the current user's row only.
      const { data, error } = await supabase
        .from("preferences")
        .select("alert_frequency, score_threshold")
        .eq("user_id", user.id)
        .maybeSingle();
      if (error) {
        setLoad("error");
        setError(error.message);
        return;
      }
      if (data) {
        setFrequency(data.alert_frequency as AlertFrequency);
        setThreshold(data.score_threshold);
      }
      setLoad("ready");
    })();
  }, []);

  async function save() {
    setSaving(true);
    setSaved(false);
    setError("");
    const supabase = createClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();
    if (!user) {
      setError("Your session expired. Please sign in again.");
      setSaving(false);
      return;
    }
    const { error } = await supabase.from("preferences").upsert(
      {
        user_id: user.id,
        alert_frequency: frequency,
        score_threshold: threshold,
      },
      { onConflict: "user_id" },
    );
    if (error) {
      setError(error.message);
    } else {
      setSaved(true);
    }
    setSaving(false);
  }

  if (load === "loading") {
    return (
      <div className="center-screen">
        <span className="spinner" />
        Loading your settings…
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 520 }}>
      <h1>Settings</h1>
      <p className="muted">Control how and when JobOps alerts you.</p>

      <div className="card">
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

        <div className="field">
          <label className="label" htmlFor="threshold">
            Score threshold: {threshold}
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

        {error && (
          <div className="alert alert-error" style={{ marginBottom: "1rem" }}>
            {error}
          </div>
        )}
        {saved && (
          <div className="alert alert-success" style={{ marginBottom: "1rem" }}>
            Settings saved.
          </div>
        )}

        <button type="button" className="btn" onClick={save} disabled={saving}>
          {saving ? (
            <>
              <span className="spinner" /> Saving…
            </>
          ) : (
            "Save settings"
          )}
        </button>
      </div>
    </div>
  );
}
