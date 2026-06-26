"use client";

import { useRouter } from "next/navigation";
import { useRef, useState, type ChangeEvent } from "react";

import { backendPost } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import type { Draft } from "@/lib/types";

type Step = "upload" | "review";
const MAX_BYTES = 10 * 1024 * 1024; // 10 MB

const toList = (value: string): string[] =>
  value
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

const fromList = (items: string[] | undefined): string =>
  (items ?? []).join(", ");

function safeName(name: string): string {
  return name.replace(/[^a-zA-Z0-9._-]/g, "_");
}

export default function OnboardingPage() {
  const router = useRouter();
  const fileInput = useRef<HTMLInputElement>(null);

  const [step, setStep] = useState<Step>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [summary, setSummary] = useState("");

  // editable draft fields
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [skills, setSkills] = useState("");
  const [domains, setDomains] = useState("");
  const [locations, setLocations] = useState("");
  const [seniority, setSeniority] = useState("");

  // gap questions
  const [targetRoles, setTargetRoles] = useState("");
  const [remotePref, setRemotePref] = useState("flexible");
  const [emailOptIn, setEmailOptIn] = useState(false);

  function onPickFile(event: ChangeEvent<HTMLInputElement>) {
    setError("");
    const picked = event.target.files?.[0] ?? null;
    if (picked && !/\.(pdf|docx)$/i.test(picked.name)) {
      setError("Please upload a PDF or DOCX file.");
      setFile(null);
      return;
    }
    if (picked && picked.size > MAX_BYTES) {
      setError("That file is larger than 10 MB.");
      setFile(null);
      return;
    }
    setFile(picked);
  }

  async function analyze() {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const supabase = createClient();
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session)
        throw new Error("Your session expired. Please sign in again.");

      const userId = session.user.id;
      const path = `${userId}/${Date.now()}-${safeName(file.name)}`;

      // Upload to the private bucket. Storage RLS confines writes to the
      // user's own "<uid>/…" folder.
      const { error: uploadError } = await supabase.storage
        .from("resumes")
        .upload(path, file, { upsert: true });
      if (uploadError) throw new Error(uploadError.message);

      // Backend downloads the file (service role), extracts text, runs the
      // onboarding agent, and returns a draft. Raw resume text stays server-side.
      const { draft } = await backendPost<{ draft: Draft }>(
        "/onboarding/parse",
        session.access_token,
        { resume_path: path },
      );

      setFullName(draft.full_name ?? "");
      setEmail(draft.email ?? session.user.email ?? "");
      setSkills(fromList(draft.skills));
      setDomains(fromList(draft.domains));
      setLocations(fromList(draft.locations));
      setSeniority(draft.seniority ?? "");
      setTargetRoles(fromList(draft.roles_held)); // a starting point — user edits
      setSummary(draft.summary ?? "");
      setStep("review");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    setBusy(true);
    setError("");
    try {
      const supabase = createClient();
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session)
        throw new Error("Your session expired. Please sign in again.");

      await backendPost("/onboarding/complete", session.access_token, {
        full_name: fullName,
        email,
        parsed: {
          skills: toList(skills),
          target_roles: toList(targetRoles),
          seniority,
          domains: toList(domains),
          locations: toList(locations),
          remote_pref: remotePref,
          comp_floor: "",
          attribution_notes: [],
        },
        preferences: { email_opt_in: emailOptIn, score_threshold: 60 },
      });

      // Land a just-onboarded user on the launcher ("what would you like to do?"),
      // not the data-heavy Dashboard. Mirrors the login-callback routing, which
      // already sends onboarded users to /home. Dashboard stays in the nav.
      router.push("/home");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
      setBusy(false);
    }
  }

  return (
    <div style={{ maxWidth: 640 }}>
      <h1>Set up your profile</h1>
      <p className="muted">
        Upload your resume and confirm a few details. We only use what&apos;s
        actually in it — nothing is invented. You can edit any field later from
        Settings without re-uploading.
      </p>

      <div className="steps">
        <div
          className={`step ${step === "upload" ? "step-active" : "step-done"}`}
        >
          <span className="step-num">1</span> Upload
        </div>
        <div className={`step ${step === "review" ? "step-active" : ""}`}>
          <span className="step-num">2</span> Review &amp; confirm
        </div>
      </div>

      {step === "upload" && (
        <div className="card">
          <div className="dropzone">
            <p className="muted" style={{ marginBottom: "1rem" }}>
              {file ? (
                <>
                  Selected: <span className="file-name">{file.name}</span>
                </>
              ) : (
                "Choose a PDF or DOCX resume (max 10 MB)."
              )}
            </p>
            <input
              ref={fileInput}
              type="file"
              accept=".pdf,.docx"
              onChange={onPickFile}
              style={{ display: "none" }}
            />
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => fileInput.current?.click()}
              disabled={busy}
            >
              {file ? "Choose a different file" : "Choose file"}
            </button>
          </div>

          {error && (
            <div className="alert alert-error" style={{ marginTop: "1rem" }}>
              {error}
            </div>
          )}

          <button
            type="button"
            className="btn btn-block"
            style={{ marginTop: "1.25rem" }}
            onClick={analyze}
            disabled={!file || busy}
          >
            {busy ? (
              <>
                <span className="spinner" /> Reading your resume…
              </>
            ) : (
              "Analyze resume"
            )}
          </button>
        </div>
      )}

      {step === "review" && (
        <>
          {summary && (
            <div
              className="alert alert-info"
              style={{ marginBottom: "1.25rem" }}
            >
              {summary}
            </div>
          )}

          <div className="card">
            <div className="card-title">What we extracted</div>
            <p className="hint" style={{ marginTop: 0, marginBottom: "1rem" }}>
              Edit anything that&apos;s off. If something is blank, add it
              yourself — we won&apos;t guess.
            </p>

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
              <label className="label" htmlFor="skills">
                Skills
              </label>
              <textarea
                id="skills"
                className="textarea"
                value={skills}
                onChange={(e) => setSkills(e.target.value)}
                placeholder="Comma-separated, e.g. Python, SQL, React"
              />
            </div>

            <div className="row">
              <div className="field">
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
            </div>
          </div>

          <div className="card">
            <div className="card-title">A few quick questions</div>

            <div className="field">
              <label className="label" htmlFor="targetRoles">
                What roles are you targeting?
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
                <label className="label" htmlFor="remotePref">
                  Location / remote preference
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
                <p className="hint">
                  Based-in locations:{" "}
                  {locations || <span className="faint">none extracted</span>}
                </p>
              </div>
              <div className="field">
                <label className="checkbox-row" htmlFor="emailOptIn">
                  <input
                    id="emailOptIn"
                    type="checkbox"
                    checked={emailOptIn}
                    onChange={(e) => setEmailOptIn(e.target.checked)}
                  />
                  <span>Email me new matches</span>
                </label>
                <p className="hint">
                  Get an email when we find new roles scored against your
                  profile.
                </p>
              </div>
            </div>
          </div>

          {error && (
            <div className="alert alert-error" style={{ marginBottom: "1rem" }}>
              {error}
            </div>
          )}

          <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
            <button
              type="button"
              className="btn"
              onClick={save}
              disabled={busy}
            >
              {busy ? (
                <>
                  <span className="spinner" /> Saving…
                </>
              ) : (
                "Confirm & save profile"
              )}
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => {
                setStep("upload");
                setError("");
              }}
              disabled={busy}
            >
              Back
            </button>
          </div>
        </>
      )}
    </div>
  );
}
