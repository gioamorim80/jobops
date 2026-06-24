"""Per-user matches actions that the client can't do directly.

`matches` is SELECT-only to authenticated clients by design (the service role is
the only writer — see migration 0007). So a user's "delete this match" goes through
the backend, scoped to the verified JWT user, mirroring the JWT-scoped writes in
ondemand.py (/ondemand/applied, /ondemand/approve). No RLS/grant change.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.auth import CurrentUserId
from app.supabase_client import get_service_client

router = APIRouter(prefix="/matches", tags=["matches"])


class DeleteMatchRequest(BaseModel):
    id: str  # the match to delete; user_id is NEVER taken from the request body


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
