"""Per-user matches actions that the client can't do directly.

`matches` is SELECT-only to authenticated clients by design (the service role is
the only writer — see migration 0007). So a user's "delete this match" goes through
the backend, scoped to the verified JWT user, mirroring the JWT-scoped writes in
ondemand.py (/ondemand/applied, /ondemand/approve). No RLS/grant change.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.auth import CurrentUserId
from app.supabase_client import get_service_client

router = APIRouter(prefix="/matches", tags=["matches"])


class DeleteMatchRequest(BaseModel):
    id: str  # the match to delete; user_id is NEVER taken from the request body


class MatchContextRequest(BaseModel):
    id: str  # the match to load context for; user_id is NEVER taken from the body


@router.post("/context")
def match_context(user_id: CurrentUserId, body: MatchContextRequest) -> dict:
    """Return just the context the score page needs to tailor a match: the posting's
    role/company and its link. Scoped to the CALLER'S OWN match — `user_id` is the
    verified-JWT id (never request input), so passing another user's match id returns
    404 rather than exposing their row. Read-only and deliberately returns no
    score/analysis: the match-arrival tailor flow re-scores the user-pasted full JD
    (the stored match was scored on the ~500-char snippet), so the stale snippet score
    is not surfaced here."""
    client = get_service_client()
    rows = (
        client.table("matches")
        .select("id, jobs ( title, company, source_url )")
        .eq("id", body.id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Match not found.")
    job = rows[0].get("jobs") or {}
    return {
        "id": rows[0]["id"],
        "title": job.get("title"),
        "company": job.get("company"),
        "source_url": job.get("source_url"),
    }


@router.post("/delete")
def delete_match(user_id: CurrentUserId, body: DeleteMatchRequest) -> dict:
    """Delete one of the CALLER'S OWN matches. The service role can touch any row,
    so isolation comes entirely from `.eq("user_id", user_id)` where `user_id` is
    the verified-JWT id (never request input) — a user can't delete another user's
    match by passing its id. A delete that matches nothing (wrong id, or not the
    caller's) is a no-op success, so the UI just refreshes."""
    client = get_service_client()
    client.table("matches").delete().eq("id", body.id).eq("user_id", user_id).execute()
    return {"ok": True}
