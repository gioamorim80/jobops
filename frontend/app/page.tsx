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
            JobOps uses AI to tailor every fit score and every résumé bullet to
            the <em>specific</em> posting — grounded only in your real
            experience. No generic matches. No inflated claims.
          </p>
          <div className="hero-actions">
            <Link href="/login" className="btn">
              Get started
            </Link>
          </div>
        </section>

        <section className="card ethos">
          <h2>Tailored to the role. True to you.</h2>
          <p className="muted">
            Most tools fire off look-alike matches and pad your application with
            things you never did. JobOps reads each posting and your real
            profile, then scores and tailors for that one role — honestly.
          </p>
          <ul className="ethos-list">
            <li>No spray-and-pray matches.</li>
            <li>No inflated bullets.</li>
            <li>No roles you&apos;d never want.</li>
            <li>
              Just honest fit, grounded in what you&apos;ve actually done.
            </li>
          </ul>
        </section>

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
              Opt into daily or weekly email alerts of new roles above your
              score threshold. Pause anytime.
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
