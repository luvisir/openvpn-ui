from fastapi import APIRouter, HTTPException

from backend.config import ConfigLoadError, get_config_path, load_config, validate_config_paths

router = APIRouter()


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
