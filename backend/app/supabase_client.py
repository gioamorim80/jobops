"""Backend Supabase client — uses the SERVICE ROLE key.

The service role bypasses RLS, so this client is backend-only and we always
scope writes to a `user_id` derived from a verified JWT (see app/auth.py),
never from request input. The key must never reach the frontend.
"""

from functools import lru_cache

from app.config import settings
from supabase import Client, create_client


@lru_cache(maxsize=1)
def get_service_client() -> Client:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError("Supabase is not configured (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY).")
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
