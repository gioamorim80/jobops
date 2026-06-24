"""/matches/delete — JWT-scoped delete (auth gate + isolation, no network)."""

import app.matches as matches_mod
import pytest
from app.auth import get_current_user_id
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


class _Resp:
    def __init__(self, data):
        self.data = data


class _FakeClient:
    """Tiny in-memory `matches` store that honors .delete().eq(...).eq(...).
    `store["rows"]` is a list of {"id", "user_id"} dicts."""

    def __init__(self, store):
        self.store = store
        self._op = None
        self._filters: dict = {}

    def table(self, name):
        self._op = None
        self._filters = {}
        return self

    def delete(self):
        self._op = "delete"
        return self

    def eq(self, col, val):
        self._filters[col] = val
        return self

    def execute(self):
        if self._op == "delete":
            hit = [
                r
                for r in self.store["rows"]
                if all(r.get(k) == v for k, v in self._filters.items())
            ]
            for r in hit:
                self.store["rows"].remove(r)
            return _Resp(hit)
        return _Resp([])


def _wire(monkeypatch, store, caller):
    monkeypatch.setattr(matches_mod, "get_service_client", lambda: _FakeClient(store))
    app.dependency_overrides[get_current_user_id] = lambda: caller


def test_delete_requires_auth() -> None:
    resp = client.post("/matches/delete", json={"id": "m1"})
    assert resp.status_code == 401


def test_deletes_own_match(monkeypatch: pytest.MonkeyPatch) -> None:
    store = {"rows": [{"id": "m1", "user_id": "user-1"}]}
    _wire(monkeypatch, store, "user-1")
    try:
        resp = client.post("/matches/delete", json={"id": "m1"})
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert store["rows"] == []  # the caller's own row is gone


def test_cannot_delete_another_users_match(monkeypatch: pytest.MonkeyPatch) -> None:
    # The row belongs to OTHER; user-1 calls delete with its id -> deletes nothing
    # (the .eq("user_id", caller) guard holds) -> no-op success, row survives.
    store = {"rows": [{"id": "m2", "user_id": "OTHER"}]}
    _wire(monkeypatch, store, "user-1")
    try:
        resp = client.post("/matches/delete", json={"id": "m2"})
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}  # no-op is a normal success, not an error
    assert store["rows"] == [{"id": "m2", "user_id": "OTHER"}]  # untouched


def test_user_id_from_jwt_not_body(monkeypatch: pytest.MonkeyPatch) -> None:
    # Row belongs to the caller (user-1); body carries a DIFFERENT user_id. If the
    # body's user_id were used, the scope would be "OTHER" and the row would NOT be
    # deleted. It IS deleted -> the JWT id was used and the body field ignored.
    store = {"rows": [{"id": "m3", "user_id": "user-1"}]}
    _wire(monkeypatch, store, "user-1")
    try:
        resp = client.post("/matches/delete", json={"id": "m3", "user_id": "OTHER"})
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)
    assert resp.status_code == 200
    assert store["rows"] == []  # deleted using the JWT user, not the body user_id
