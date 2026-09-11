from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.command_runner import CommandError, run_configured_command
from backend.config import ConfigLoadError, load_config
from backend.database import add_audit_event, set_user_disabled
from backend.users import list_users

router = APIRouter()


class CreateUserRequest(BaseModel):
    common_name: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)
    reason: str = ""


class UserActionRequest(BaseModel):
    reason: str = ""
    confirmation: str = ""


@router.get("")
def users() -> dict[str, object]:
    try:
        config = load_config()
        return {"users": list_users(config)}
    except ConfigLoadError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("")
def create_user(payload: CreateUserRequest) -> dict[str, object]:
    config = _load()
    if not config.features.allow_create_user:
        raise HTTPException(status_code=403, detail="Create user feature is disabled")
    try:
        result = run_configured_command(
            config.lifecycle.create_user_command,
            payload.common_name,
            payload.reason,
            payload.password,
        )
        add_audit_event(config, "user.created", payload.common_name, payload.reason)
        return {"result": "created", "stdout": result.stdout}
    except CommandError as exc:
        add_audit_event(
            config, "user.created", payload.common_name, payload.reason, "failed", str(exc)
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{common_name}/disable")
def disable_user(common_name: str, payload: UserActionRequest) -> dict[str, object]:
    config = _load()
    if not config.features.allow_disable_user:
        raise HTTPException(status_code=403, detail="Disable user feature is disabled")
    try:
        if config.lifecycle.disable_user_command:
            run_configured_command(config.lifecycle.disable_user_command, common_name, payload.reason)
        set_user_disabled(config, common_name, True)
        add_audit_event(config, "user.disabled", common_name, payload.reason)
        return {"result": "disabled", "common_name": common_name}
    except CommandError as exc:
        add_audit_event(config, "user.disabled", common_name, payload.reason, "failed", str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{common_name}/enable")
def enable_user(common_name: str, payload: UserActionRequest) -> dict[str, object]:
    config = _load()
    if not config.features.allow_disable_user:
        raise HTTPException(status_code=403, detail="Enable user feature is disabled")
    try:
        if config.lifecycle.enable_user_command:
            run_configured_command(config.lifecycle.enable_user_command, common_name, payload.reason)
        set_user_disabled(config, common_name, False)
        add_audit_event(config, "user.enabled", common_name, payload.reason)
        return {"result": "enabled", "common_name": common_name}
    except CommandError as exc:
        add_audit_event(config, "user.enabled", common_name, payload.reason, "failed", str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{common_name}/revoke")
def revoke_user(common_name: str, payload: UserActionRequest) -> dict[str, object]:
    config = _load()
    if not config.features.allow_revoke_user:
        raise HTTPException(status_code=403, detail="Revoke user feature is disabled")
    if payload.confirmation != common_name:
        raise HTTPException(status_code=400, detail="Confirmation must match common name")
    if not payload.reason:
        raise HTTPException(status_code=400, detail="Reason is required")
    try:
        result = run_configured_command(config.lifecycle.revoke_user_command, common_name, payload.reason)
        add_audit_event(config, "user.revoked", common_name, payload.reason)
        return {"result": "revoked", "stdout": result.stdout}
    except CommandError as exc:
        add_audit_event(config, "user.revoked", common_name, payload.reason, "failed", str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _load():
    try:
        return load_config()
    except ConfigLoadError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
