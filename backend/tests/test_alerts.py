"""Sent-state helper tests — threshold gate, idempotent mark, per-user isolation.

No network: a tiny in-memory fake client backs the `preferences`, `matches`, and
`alerts_log` tables and honors the query builder used by app.alerts (select + eq/
gte/order/limit, and upsert with on_conflict + ignore_duplicates enforcing the
UNIQUE(user_id, match_id) dedup).
"""

from app.alerts import mark_matches_sent, unsent_matches_for_user


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

    # builders
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

    def order(self, *a, **k) -> "_Query":
        return self

    def limit(self, *a, **k) -> "_Query":
        return self

    def _matches(self, row: dict) -> bool:
        for kind, col, val in self.filters:
            if kind == "eq" and row.get(col) != val:
                return False
            if kind == "gte" and not (row.get(col) is not None and row.get(col) >= val):
                return False
        return True

    def execute(self) -> _Resp:
        rows = self.store.setdefault(self.table, [])
        if self.op == "select":
            return _Resp([dict(r) for r in rows if self._matches(r)])
        if self.op == "upsert":
            inserted = []
            for new in self._rows:
                clash = any(
                    r["user_id"] == new["user_id"] and r["match_id"] == new["match_id"]
                    for r in rows
                )
                if clash:
                    if self._ignore_dup:
                        continue  # ON CONFLICT DO NOTHING
                    raise AssertionError("unexpected unique-constraint conflict")
                rows.append(dict(new))
                inserted.append(dict(new))
            return _Resp(inserted)
        return _Resp([])


class _FakeClient:
    def __init__(self, store: dict) -> None:
        self.store = store

    def table(self, name: str) -> _Query:
        return _Query(self.store, name)


# --------------------------- unsent_matches_for_user ---------------------------
def test_unsent_returns_above_threshold_without_alert() -> None:
    store = {
        "preferences": [{"user_id": "A", "score_threshold": 60}],
        "matches": [
            {"id": "m1", "user_id": "A", "score": 80},  # above, unsent -> included
            {"id": "m2", "user_id": "A", "score": 50},  # below threshold -> excluded
            {"id": "m3", "user_id": "A", "score": 70},  # above but already sent
        ],
        "alerts_log": [{"user_id": "A", "match_id": "m3", "channel": "email"}],
    }
    unsent = unsent_matches_for_user(_FakeClient(store), "A")
    assert [m["id"] for m in unsent] == ["m1"]


def test_unsent_honors_threshold_boundary_inclusive() -> None:
    # score == threshold is included (the gate is inclusive, matching /matches).
    store = {
        "preferences": [{"user_id": "A", "score_threshold": 70}],
        "matches": [
            {"id": "m1", "user_id": "A", "score": 70},  # == threshold -> included
            {"id": "m2", "user_id": "A", "score": 69},  # just below -> excluded
        ],
        "alerts_log": [],
    }
    unsent = unsent_matches_for_user(_FakeClient(store), "A")
    assert [m["id"] for m in unsent] == ["m1"]


def test_unsent_uses_default_threshold_when_no_prefs() -> None:
    # No preferences row -> default 60 applies (reuse of the same rule/default).
    store = {
        "preferences": [],
        "matches": [
            {"id": "m1", "user_id": "A", "score": 65},  # >= 60 -> included
            {"id": "m2", "user_id": "A", "score": 55},  # < 60 -> excluded
        ],
        "alerts_log": [],
    }
    unsent = unsent_matches_for_user(_FakeClient(store), "A")
    assert [m["id"] for m in unsent] == ["m1"]


# ------------------------------ mark_matches_sent ------------------------------
def test_mark_inserts_then_second_call_is_noop() -> None:
    store: dict = {"alerts_log": []}
    client = _FakeClient(store)

    first = mark_matches_sent(client, "A", ["m1", "m2"])
    assert first == 2
    assert len(store["alerts_log"]) == 2

    # Calling again for the same (user, match) is a safe no-op (ON CONFLICT DO
    # NOTHING) — no crash, no duplicate rows.
    second = mark_matches_sent(client, "A", ["m1", "m2"])
    assert second == 0
    assert len(store["alerts_log"]) == 2


def test_mark_empty_is_noop() -> None:
    store: dict = {"alerts_log": []}
    assert mark_matches_sent(_FakeClient(store), "A", []) == 0
    assert store["alerts_log"] == []


# --------------------------------- isolation ----------------------------------
def test_unsent_query_is_scoped_to_user() -> None:
    store = {
        "preferences": [],
        "matches": [
            {"id": "m1", "user_id": "A", "score": 90},
            {"id": "m2", "user_id": "B", "score": 90},
        ],
        "alerts_log": [],
    }
    a_unsent = unsent_matches_for_user(_FakeClient(store), "A")
    assert [m["id"] for m in a_unsent] == ["m1"]  # never B's match


def test_send_to_one_user_does_not_count_for_another() -> None:
    # Per-user dedup: marking A's match sent must not suppress B's own matches.
    store = {
        "preferences": [],
        "matches": [
            {"id": "ma", "user_id": "A", "score": 90},
            {"id": "mb", "user_id": "B", "score": 90},
        ],
        "alerts_log": [],
    }
    client = _FakeClient(store)
    mark_matches_sent(client, "A", ["ma"])

    assert [m["id"] for m in unsent_matches_for_user(client, "A")] == []  # A's is sent
    assert [m["id"] for m in unsent_matches_for_user(client, "B")] == ["mb"]  # B unaffected
