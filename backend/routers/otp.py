import hmac
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, Field

from backend.config import ConfigLoadError, load_config
from backend.otp_store import OTPError, OTPStore

router = APIRouter()


def admin_store(response: Response, authorization: Optional[str] = Header(default=None)):
    response.headers["Cache-Control"] = "no-store"
    try:
        store = OTPStore(load_config())
    except (OTPError, ConfigLoadError, OSError, ValueError) as exc:
        raise HTTPException(503, "OTP is disabled or not initialized") from exc
    if not hmac.compare_digest(authorization or "", "Bearer " + store.admin_token):
        raise HTTPException(401, "OTP administrator credential required")
    return store


class PolicyRequest(BaseModel):
    enforced: bool
    confirmation: str


class EnrollmentRequest(BaseModel):
    confirmation: str = ""


class ConfirmationRequest(BaseModel):
    code: str = Field(pattern=r"^[0-9]{6}$")


@router.get("")
def status(store: OTPStore = Depends(admin_store)):
    return store.status()


@router.post("/policy")
def policy(payload: PolicyRequest, store: OTPStore = Depends(admin_store)):
    expected = "ENABLE" if payload.enforced else "DISABLE"
    if payload.confirmation != expected:
        raise HTTPException(400, "Policy confirmation does not match")
    store.set_enforced(payload.enforced)
    return store.status()


@router.post("/users/{name}/enroll")
def enroll(name: str, payload: EnrollmentRequest, store: OTPStore = Depends(admin_store)):
    try:
        return store.enroll(name, payload.confirmation)
    except OTPError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/users/{name}/confirm")
def confirm(name: str, payload: ConfirmationRequest, store: OTPStore = Depends(admin_store)):
    try:
        store.confirm(name, payload.code)
        return {"result": "bound"}
    except OTPError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/users/{name}/cancel")
def cancel(name: str, store: OTPStore = Depends(admin_store)):
    store.cancel(name)
    return {"result": "cancelled"}
