"""JobOps FastAPI app — M0 skeleton.

Two endpoints:
- GET /health      → liveness probe, returns {"status": "ok"}.
- GET /agent/ping  → makes a real Anthropic call and returns the model's text,
                     proving the agent brain works end to end.
"""

import traceback
from typing import Annotated

import anthropic
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.admin import router as admin_router
from app.applog import get_logger
from app.config import settings
from app.enrich import router as enrich_router
from app.onboarding import router as onboarding_router
from app.ondemand import router as ondemand_router

logger = get_logger("jobops.errors")

app = FastAPI(title="JobOps API", version="0.1.0")


# Server-side visibility for 5xx (Railway/stdout). These DO NOT change what the
# client receives — the response body/status are identical to FastAPI's defaults,
# so the user-facing "coffee" message is unchanged. We never log secrets, auth
# headers, request bodies, resume text, or profile contents — only the route,
# status, exception type/message, and a traceback.
def _log_5xx(request: Request, exc: Exception, status_code: int) -> None:
    logger.error(
        "%s on %s %s -> %s: %s\n%s",
        type(exc).__name__,
        request.method,
        request.url.path,
        status_code,
        exc,
        "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
    )


@app.exception_handler(StarletteHTTPException)
async def _http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    # Log only server errors; 4xx are normal client outcomes. Then return the
    # SAME response FastAPI's default handler would (detail + status + headers).
    if exc.status_code >= 500:
        _log_5xx(request, exc, exc.status_code)
    return JSONResponse(
        {"detail": exc.detail},
        status_code=exc.status_code,
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Truly unhandled error → log it, then return the generic 500 (same status the
    # default would; the client still shows its "coffee" message for any >= 500).
    _log_5xx(request, exc, 500)
    return JSONResponse({"detail": "Internal Server Error"}, status_code=500)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(onboarding_router)
app.include_router(ondemand_router)
app.include_router(enrich_router)
app.include_router(admin_router)


def get_anthropic_client() -> anthropic.Anthropic:
    """Build an Anthropic client from env config, or 503 if the key is missing."""
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY is not configured on the server.",
        )
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


ClientDep = Annotated[anthropic.Anthropic, Depends(get_anthropic_client)]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/agent/ping")
def agent_ping(client: ClientDep) -> dict[str, str]:
    """Make a real, minimal Anthropic call and return the model's reply text."""
    try:
        message = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=256,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "You are the JobOps agent brain. Reply with one short "
                        "sentence confirming you are online and ready."
                    ),
                }
            ],
        )
    except anthropic.APIError as exc:
        raise HTTPException(status_code=502, detail=f"Anthropic API error: {exc}") from exc

    text = "".join(block.text for block in message.content if block.type == "text")
    return {"model": message.model, "text": text}
