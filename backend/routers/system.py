from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.command_runner import CommandError, run_configured_command
from backend.config import ConfigLoadError, get_config_path, load_config, validate_config_paths
from backend.database import add_audit_event

router = APIRouter()


class OpenVPNReloadRequest(BaseModel):
    confirmation: str = ""
    reason: str = ""


@router.get("/health")
def health() -> dict[str, object]:
    try:
        config = load_config()
    except ConfigLoadError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    path_checks = validate_config_paths(config)
    missing_required = [
        check
        for check in path_checks
        if check["status"] != "ok"
        and check["name"]
        in {
            "server.config_path",
            "certificates.ca_dir",
            "certificates.issued_dir",
            "certificates.private_dir",
            "certificates.crl_path",
            "certificates.client_profiles_dir",
        }
    ]

    return {
        "status": "degraded" if missing_required else "ok",
        "config_loaded": True,
        "config_path": str(get_config_path()),
        "path_checks": path_checks,
    }


@router.get("/config")
def config() -> dict[str, object]:
    try:
        loaded = load_config()
    except ConfigLoadError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"config_path": str(get_config_path()), **loaded.sanitized()}


@router.post("/openvpn/reload")
def reload_openvpn(payload: OpenVPNReloadRequest) -> dict[str, object]:
    try:
        loaded = load_config()
    except ConfigLoadError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if not loaded.features.allow_openvpn_reload:
        raise HTTPException(status_code=403, detail="OpenVPN reload feature is disabled")
    if payload.confirmation != "restart":
        raise HTTPException(status_code=400, detail="Confirmation must be restart")

    try:
        result = run_configured_command(
            loaded.lifecycle.reload_command,
            "openvpn",
            reason=payload.reason,
            timeout_seconds=loaded.lifecycle.command_timeout_seconds,
        )
        add_audit_event(loaded, "openvpn.restarted", loaded.server.service_name, payload.reason)
        return {"result": "restarted", "stdout": result.stdout}
    except CommandError as exc:
        add_audit_event(
            loaded,
            "openvpn.restarted",
            loaded.server.service_name,
            payload.reason,
            "failed",
            str(exc),
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc
