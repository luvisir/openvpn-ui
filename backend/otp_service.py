"""Run separately from the panel: python -m uvicorn backend.otp_service:app ..."""
import hmac
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from backend.config import load_config
from backend.otp_store import OTPStore


@asynccontextmanager
async def lifespan(app):
    app.state.store = OTPStore(load_config())
    yield


app = FastAPI(title="OpenVPN OTP verifier", docs_url=None, redoc_url=None,
              openapi_url=None, lifespan=lifespan)


class VerificationRequest(BaseModel):
    node: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    common_name: str = Field(min_length=1, max_length=128)
    username: str = Field(min_length=1, max_length=128)
    code: str = Field(max_length=256)


@app.get("/health")
def health():
    # Read the database too, so a live process with unavailable storage is not healthy.
    with app.state.store.connect() as db:
        db.execute("SELECT enforced FROM settings WHERE id=1").fetchone()
    return {"status": "ok"}


@app.post("/verify")
def verify(payload: VerificationRequest, authorization: Optional[str] = Header(default=None)):
    store = app.state.store
    token = store.node_tokens.get(payload.node)
    if not token or not hmac.compare_digest(authorization or "", "Bearer " + token):
        raise HTTPException(401, "Node authentication failed")
    try:
        allowed = store.verify(payload.node, payload.common_name, payload.username, payload.code)
    except Exception as exc:
        # Never reflect submitted passwords, encrypted secrets or database errors.
        raise HTTPException(503, "OTP authentication unavailable") from exc
    return {"allowed": allowed}
