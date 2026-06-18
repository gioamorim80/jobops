import Link from "next/link";

import { AgentStatus } from "@/components/AgentStatus";

export default function Home() {
  return (
    <div className="container">
      <header className="hero">
        <span className="badge" style={{ marginBottom: "1.25rem" }}>
          <span className="dot dot-ok" /> Multi-tenant · agentic
        </span>
        <h1>Land the right role, faster.</h1>
        <p className="lead">
          JobOps reads your resume, scores real job postings against your actual
          experience, and tailors honest application material — never inventing
          anything you didn&apos;t do.
        </p>
        <div className="hero-actions">
          <Link href="/login" className="btn">
            Get started
          </Link>
          <a
            href="https://github.com/gioamorim80/jobops"
            className="btn btn-ghost"
            target="_blank"
            rel="noreferrer"
          >
            View the repo
          </a>
        </div>
        <div style={{ marginTop: "1.5rem" }}>
          <AgentStatus />
        </div>
      </header>

      <section className="feature-grid">
        <div className="card">
          <div className="card-title">Paste a link, get a fit score</div>
          <p className="muted" style={{ margin: 0 }}>
            An instant 0–100 fit score with the requirements you clear and the
            honest gaps — grounded in your real profile.
          </p>
        </div>
        <div className="card">
          <div className="card-title">Tailored, truthful bullets</div>
          <p className="muted" style={{ margin: 0 }}>
            Reorders and rephrases what&apos;s true on your resume. It never
            fabricates titles, metrics, or skills.
          </p>
        </div>
        <div className="card">
          <div className="card-title">Recurring scored matches</div>
          <p className="muted" style={{ margin: 0 }}>
            Opt into daily or weekly email alerts of new roles above your score
            threshold. Pause anytime.
          </p>
        </div>
      </section>
    </div>
  );
}
