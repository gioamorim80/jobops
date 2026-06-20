import Link from "next/link";

export default function Home() {
  return (
    <>
      <header className="app-header">
        <div className="container app-header-inner">
          <Link href="/" className="brand">
            JobOps
          </Link>
          <div className="app-header-right">
            <Link href="/login">Sign in</Link>
          </div>
        </div>
      </header>

      <div className="container">
        <section className="hero">
          <h1>A calmer way to find your next role.</h1>
          <p className="lead">
            JobOps reads each posting in full and reasons against your real
            experience — purpose-built analysis, not keyword matching — to score
            your fit and tailor every résumé bullet to that one role. Grounded
            only in what you&apos;ve actually done.
          </p>
          <div className="hero-actions">
            <Link href="/login" className="btn">
              Get started
            </Link>
          </div>
        </section>

        <section className="feature-grid">
          <div className="card">
            <div className="card-title">Paste a link, get a fit score</div>
            <p className="muted" style={{ margin: 0 }}>
              An instant 0–100 fit score with a clear band, the requirements you
              clear, and the honest gaps — grounded in your real profile.
            </p>
          </div>
          <div className="card">
            <div className="card-title">Suggested changes to your résumé</div>
            <p className="muted" style={{ margin: 0 }}>
              Edits tailored to the posting, each showing where it applies. It
              reorders and rephrases what&apos;s true — never invents titles,
              metrics, or skills.
            </p>
          </div>
          <div className="card">
            <div className="card-title">An honest coach</div>
            <p className="muted" style={{ margin: 0 }}>
              A warm, in-scope chat to add the true context your résumé missed —
              what you built, who really owned what, a title the timeline
              flattened. Nothing&apos;s saved unless you confirm.
            </p>
          </div>
          <div className="card">
            <div className="card-title">
              Recurring scored matches
              <span className="soon">Coming soon</span>
            </div>
            <p className="muted" style={{ margin: 0 }}>
              Soon: opt into daily or weekly emails of new roles scored against
              your profile. It won&apos;t fling your résumé at jobs you&apos;d
              never want — only honest fits.
            </p>
          </div>
        </section>
      </div>

      <footer className="site-footer">
        <div className="container site-footer-inner">
          <span className="faint">JobOps</span>
          <a
            href="https://github.com/gioamorim80/jobops"
            target="_blank"
            rel="noreferrer"
          >
            View the repo
          </a>
        </div>
      </footer>
    </>
  );
}
