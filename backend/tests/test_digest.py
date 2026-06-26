"""Digest per-user logic — double-gate, top-N, mark-only-on-success, PII-safe.

No network, no LLM: send_email is monkeypatched and an in-memory fake client backs
preferences/profiles/matches/alerts_log. The fake honors the query builder used by
app.digest + app.alerts (select/eq/gte/order/limit and upsert with on_conflict +
ignore_duplicates), including the embedded `jobs` on matches rows.
"""

import app.digest as digest_mod
from app.alerts import unsent_matches_for_user
from app.digest import compose_digest_html, send_user_digest, send_user_reinvite


class _Resp:
    def __init__(self, data: list) -> None:
        self.data = data


class _Query:
    def __init__(self, store: dict, table: str) -> None:
        self.store = store
        self.table = table
        self.op = "select"
        self.filters: list = []
        self._rows: list = []
        self._ignore_dup = False
        self._order: tuple | None = None

    def select(self, *a, **k) -> "_Query":
        self.op = "select"
        return self

    def upsert(self, rows, on_conflict=None, ignore_duplicates=False, **k) -> "_Query":
        self.op = "upsert"
        self._rows = rows if isinstance(rows, list) else [rows]
        self._ignore_dup = ignore_duplicates
        return self

    def eq(self, col, val) -> "_Query":
        self.filters.append(("eq", col, val))
        return self

    def gte(self, col, val) -> "_Query":
        self.filters.append(("gte", col, val))
        return self

    def order(self, col, desc=False) -> "_Query":
        self._order = (col, desc)
        return self

    def limit(self, *a, **k) -> "_Query":
        return self

    def _ok(self, row: dict) -> bool:
        for kind, col, val in self.filters:
            if kind == "eq" and row.get(col) != val:
                return False
            if kind == "gte" and not (row.get(col) is not None and row.get(col) >= val):
                return False
        return True

    def execute(self) -> _Resp:
        rows = self.store.setdefault(self.table, [])
        if self.op == "select":
            hit = [dict(r) for r in rows if self._ok(r)]
            if self._order:
                col, desc = self._order
                hit.sort(key=lambda r: r.get(col) or 0, reverse=desc)
            return _Resp(hit)
        if self.op == "upsert":
            inserted = []
            for new in self._rows:
                clash = any(
                    r["user_id"] == new["user_id"] and r["match_id"] == new["match_id"]
                    for r in rows
                )
                if clash and self._ignore_dup:
                    continue
                rows.append(dict(new))
                inserted.append(dict(new))
            return _Resp(inserted)
        return _Resp([])


class _FakeClient:
    def __init__(self, store: dict) -> None:
        self.store = store

    def table(self, name: str) -> _Query:
        return _Query(self.store, name)


def _match(mid: str, score: int, title="Data Scientist", company="Acme", analysis="Great fit."):
    return {
        "id": mid,
        "user_id": "A",
        "score": score,
        "band": "Strong fit",
        "decision": "APPLY",
        "analysis": analysis,
        "jobs": {"title": title, "company": company, "source_url": "https://x"},
    }


def _ok_sender(captured: list):
    def fake_send(to, subject, html, text=None):
        captured.append({"to": to, "subject": subject, "html": html, "text": text})
        return {"status": "ok", "id": "msg_1"}

    return fake_send


def _base_store(opt_in=True, matches=None):
    return {
        "preferences": [{"user_id": "A", "email_opt_in": opt_in, "score_threshold": 60}],
        # raw_resume_text present in the row but must NEVER appear in the email.
        "profiles": [
            {"user_id": "A", "email": "a@example.com", "raw_resume_text": "SECRET_RESUME"}
        ],
        "matches": matches if matches is not None else [],
        "alerts_log": [],
    }


def test_targeted_user_sends_and_marks_topN(monkeypatch) -> None:
    monkeypatch.setattr(digest_mod.settings, "digest_max_matches", 2)
    captured: list = []
    monkeypatch.setattr(digest_mod, "send_email", _ok_sender(captured))
    store = _base_store(matches=[_match("m1", 90), _match("m2", 80), _match("m3", 70)])
    client = _FakeClient(store)

    result = send_user_digest(client, "A")

    assert result["status"] == "sent"
    assert result["sent"] == 2 and result["marked"] == 2  # top-N respected
    assert len(captured) == 1
    assert "2 new matches" in captured[0]["subject"]
    # Exactly the top 2 (m1, m2) are marked; m3 stays unsent for next time.
    sent_ids = {r["match_id"] for r in store["alerts_log"]}
    assert sent_ids == {"m1", "m2"}
    assert [m["id"] for m in unsent_matches_for_user(client, "A")] == ["m3"]


def test_paused_user_is_skipped(monkeypatch) -> None:
    # A paused (inactivity) user is not digested, even with qualifying matches.
    captured: list = []
    monkeypatch.setattr(digest_mod, "send_email", _ok_sender(captured))
    store = _base_store(matches=[_match("m1", 90)])
    store["preferences"][0]["paused"] = True
    result = send_user_digest(_FakeClient(store), "A")

    assert result["status"] == "skipped_paused"
    assert captured == []  # not emailed while paused


def test_reinvite_is_pii_safe_and_uses_mailer(monkeypatch) -> None:
    captured: list = []
    monkeypatch.setattr(digest_mod, "send_email", _ok_sender(captured))
    store = {
        "profiles": [{"user_id": "A", "email": "a@example.com", "raw_resume_text": "SECRET_RESUME"}]
    }
    result = send_user_reinvite(_FakeClient(store), "A")

    assert result["status"] == "ok"
    sent = captured[0]
    assert sent["to"] == "a@example.com"
    body = sent["html"] + (sent["text"] or "")
    assert "SECRET_RESUME" not in body  # no PII in the reinvite
    assert "/home" in body  # links back into the app (returning auto-unpauses)


def test_opted_out_user_targeted_is_skipped(monkeypatch) -> None:
    captured: list = []
    monkeypatch.setattr(digest_mod, "send_email", _ok_sender(captured))
    store = _base_store(opt_in=False, matches=[_match("m1", 90)])
    client = _FakeClient(store)

    result = send_user_digest(client, "A")

    assert result["status"] == "skipped_opt_out"
    assert captured == []  # never emailed someone who opted out
    assert store["alerts_log"] == []  # nothing marked


def test_no_unsent_matches_skips_silently(monkeypatch) -> None:
    captured: list = []
    monkeypatch.setattr(digest_mod, "send_email", _ok_sender(captured))
    # One match but it's below threshold (60) -> nothing qualifies.
    store = _base_store(matches=[_match("m1", 55)])
    client = _FakeClient(store)

    result = send_user_digest(client, "A")

    assert result["status"] == "skipped_no_matches"
    assert captured == []  # no empty digest


def test_not_marked_when_send_fails(monkeypatch) -> None:
    def failing_send(to, subject, html, text=None):
        return {"status": "error", "error": "resend_error", "status_code": 422}

    monkeypatch.setattr(digest_mod, "send_email", failing_send)
    store = _base_store(matches=[_match("m1", 90), _match("m2", 80)])
    client = _FakeClient(store)

    result = send_user_digest(client, "A")

    assert result["status"] == "send_failed"
    assert store["alerts_log"] == []  # NOT marked -> re-surfaces next run
    assert len(unsent_matches_for_user(client, "A")) == 2


def test_email_is_score_only_and_pii_safe(monkeypatch) -> None:
    captured: list = []
    monkeypatch.setattr(digest_mod, "send_email", _ok_sender(captured))
    store = _base_store(matches=[_match("m1", 88, analysis="Strong Python overlap.")])
    client = _FakeClient(store)

    send_user_digest(client, "A")

    body = captured[0]["html"] + (captured[0]["text"] or "")
    # Score-only fields present:
    assert "Data Scientist — Acme" in body
    assert "Fit 88" in body
    assert "Strong Python overlap." in body  # the one-line pitch
    assert "/score?match=m1" in body  # routes into the in-app tailor flow
    # PII NEVER present: the profile's resume text must not leak into the email.
    assert "SECRET_RESUME" not in body


def test_compose_escapes_and_has_no_external_assets() -> None:
    # Defense: a hostile title is escaped; no external CSS/JS in the markup.
    html = compose_digest_html([_match("m1", 90, title="<script>x</script>", company="C")])
    assert "<script>x</script>" not in html
    assert "&lt;script&gt;" in html
    assert "<link" not in html and "</script>" not in html
