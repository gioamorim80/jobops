"""Auth dependency — derive the caller's user_id from their Supabase JWT.

The frontend sends the user's access token as `Authorization: Bearer <jwt>`.
We verify it against Supabase (signing-method agnostic) and return the user id.
The user_id is NEVER taken from request input — only from the verified token —
so a caller can never act on another tenant's rows.
"""

from typing import Annotated

from fastapi import Depends, Header, HTTPException

from app.supabase_client import get_service_client


def get_current_user_id(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header.")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token.")
    try:
        result = get_service_client().auth.get_user(token)
    except HTTPException:
        raise
    except Exception as exc:  # network / config / invalid token
        raise HTTPException(status_code=401, detail="Could not verify session.") from exc

    user = getattr(result, "user", None)
    if user is None or not getattr(user, "id", None):
        raise HTTPException(status_code=401, detail="Invalid or expired session.")
    return str(user.id)


CurrentUserId = Annotated[str, Depends(get_current_user_id)]
