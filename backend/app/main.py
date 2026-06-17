"""JobOps FastAPI app — M0 skeleton.

Two endpoints:
- GET /health      → liveness probe, returns {"status": "ok"}.
- GET /agent/ping  → makes a real Anthropic call and returns the model's text,
                     proving the agent brain works end to end.
"""

from typing import Annotated

import anthropic
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

app = FastAPI(title="JobOps API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
