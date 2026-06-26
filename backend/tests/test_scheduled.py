"""Scheduled run-and-exit entrypoint tests — order, budget interaction, resilience,
exit codes, PII-safe logging. No network: the client, scan, and digest are all
monkeypatched. Log capture uses a handler on the module logger (propagate=False)."""

import logging

import app.scheduled as scheduled_mod


class _CaptureHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def _no_client(monkeypatch) -> None:
    monkeypatch.setattr(scheduled_mod, "get_service_client", lambda: object())


def test_runs_scan_then_digest_in_order(monkeypatch) -> None:
    _no_client(monkeypatch)
    order: list[str] = []

    def fake_scan(client):
        order.append("scan")
        return {"status": "ok", "scanned": 2}

    def fake_digest(client):
        order.append("digest")
        return {"targeted": 2, "sent": 1}

    monkeypatch.setattr(scheduled_mod, "scan_all_opted_in", fake_scan)
    monkeypatch.setattr(scheduled_mod, "digest_all_opted_in", fake_digest)

    code = scheduled_mod.run()
    assert order == ["scan", "digest"]  # scan completes before digest
    assert code == 0


def test_digest_runs_even_when_scan_over_budget(monkeypatch) -> None:
    _no_client(monkeypatch)
    called: list[str] = []

    monkeypatch.setattr(
        scheduled_mod,
        "scan_all_opted_in",
        lambda client: {"status": "budget_exceeded", "scanned": 0, "stopped_on_budget": True},
    )

    def fake_digest(client):
        called.append("digest")
        return {"targeted": 3, "sent": 2}

    monkeypatch.setattr(scheduled_mod, "digest_all_opted_in", fake_digest)

    code = scheduled_mod.run()
    assert called == ["digest"]  # over-budget scan does NOT stop the digest
    assert code == 0  # over-budget is a normal outcome, not a failure


def test_scan_failure_still_runs_digest_and_exits_nonzero(monkeypatch) -> None:
    _no_client(monkeypatch)
    called: list[str] = []

    def boom(client):
        raise RuntimeError("scan boom")

    def fake_digest(client):
        called.append("digest")
        return {"targeted": 1, "sent": 1}

    monkeypatch.setattr(scheduled_mod, "scan_all_opted_in", boom)
    monkeypatch.setattr(scheduled_mod, "digest_all_opted_in", fake_digest)

    code = scheduled_mod.run()
    assert called == ["digest"]  # digest still runs despite the scan failing
    assert code == 1  # the run is visibly failed


def test_digest_failure_exits_nonzero(monkeypatch) -> None:
    _no_client(monkeypatch)
    monkeypatch.setattr(scheduled_mod, "scan_all_opted_in", lambda client: {"status": "ok"})

    def boom(client):
        raise RuntimeError("digest boom")

    monkeypatch.setattr(scheduled_mod, "digest_all_opted_in", boom)

    assert scheduled_mod.run() == 1


def test_both_succeed_exits_zero(monkeypatch) -> None:
    _no_client(monkeypatch)
    monkeypatch.setattr(scheduled_mod, "scan_all_opted_in", lambda client: {"status": "ok"})
    monkeypatch.setattr(
        scheduled_mod, "digest_all_opted_in", lambda client: {"targeted": 0, "sent": 0}
    )
    assert scheduled_mod.run() == 0


def test_logs_are_pii_safe(monkeypatch) -> None:
    _no_client(monkeypatch)
    # Summaries carry a planted "SECRET" inside results; run() must log COUNTS only,
    # never the result bodies — so SECRET must not appear in the logs.
    monkeypatch.setattr(
        scheduled_mod,
        "scan_all_opted_in",
        lambda client: {
            "status": "ok",
            "scanned": 1,
            "paused_now": 0,
            "skipped_paused": 0,
            "unpaused": 0,
            "stopped_on_budget": False,
            "results": [{"user": "u1", "status": "ok", "leak": "SECRET_RESUME"}],
        },
    )
    monkeypatch.setattr(
        scheduled_mod,
        "digest_all_opted_in",
        lambda client: {
            "targeted": 1,
            "sent": 1,
            "results": [{"user": "u1", "status": "sent", "leak": "SECRET_PROFILE"}],
        },
    )

    handler = _CaptureHandler()
    scheduled_mod.logger.addHandler(handler)
    try:
        scheduled_mod.run()
    finally:
        scheduled_mod.logger.removeHandler(handler)

    logged = " ".join(handler.messages)
    assert "SECRET" not in logged  # result bodies never logged
    assert "scanned=1" in logged and "sent=1" in logged  # counts are
