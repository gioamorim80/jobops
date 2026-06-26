"""Run-and-exit scheduler entrypoint for the Railway native cron service (M5 step 6).

`python -m app.scheduled` runs the scanner then the digest ONCE and exits. This is
NOT a server and NOT an in-process scheduler — the Railway cron service invokes it on
a timer (creating that service is operator dashboard work). A run-and-exit job avoids
the in-process pitfalls for a money-spending, user-emailing task (redeploy-miss,
multi-replica double-fire).

Order: scan MUST finish before digest, so the digest emails freshly-scored matches.
Budget: if scanning is over budget, the digest STILL runs — it's free and emails
already-scored matches; its own gates (opt-in, not paused, threshold) pick recipients.
Resilience: scan and digest are each wrapped, so one failing never aborts the other;
the process exits non-zero if EITHER failed, so a bad run is visibly failed. Logs are
counts/status only (PII-safe).
"""

import sys

from app.applog import get_logger
from app.digest import digest_all_opted_in
from app.scanner import scan_all_opted_in
from app.supabase_client import get_service_client

logger = get_logger("jobops.scheduled")


def run() -> int:
    """Scan-all then digest-all, once. Returns a process exit code: 0 on success, 1 if
    the scan OR the digest raised (over-budget is a normal scan outcome, not a failure)."""
    logger.info("scheduled run: starting scan then digest")
    client = get_service_client()
    failed = False

    # 1) Scanner (already budget- + inactivity-gated). Catch so a scan failure cannot
    #    stop the digest from running on existing matches.
    try:
        scan = scan_all_opted_in(client)
        logger.info(
            "scheduled scan: status=%s scanned=%s paused_now=%s skipped_paused=%s "
            "unpaused=%s stopped_on_budget=%s",
            scan.get("status"),
            scan.get("scanned"),
            scan.get("paused_now"),
            scan.get("skipped_paused"),
            scan.get("unpaused"),
            scan.get("stopped_on_budget"),
        )
    except Exception:
        failed = True
        logger.exception("scheduled scan FAILED")

    # 2) Digest — runs regardless of the scan outcome, including budget_exceeded: it
    #    spends nothing and emails already-scored matches.
    try:
        digest = digest_all_opted_in(client)
        logger.info(
            "scheduled digest: targeted=%s sent=%s",
            digest.get("targeted"),
            digest.get("sent"),
        )
    except Exception:
        failed = True
        logger.exception("scheduled digest FAILED")

    logger.info("scheduled run: done failed=%s", failed)
    return 1 if failed else 0


def main() -> None:
    # Cron job: the process MUST terminate. Exit code makes a failed run visible.
    sys.exit(run())


if __name__ == "__main__":
    main()
