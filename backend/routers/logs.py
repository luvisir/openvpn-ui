from fastapi import APIRouter, HTTPException, Query

from backend.config import ConfigLoadError, load_config
from backend.database import list_audit_events

router = APIRouter()


@router.get("/openvpn")
def openvpn_logs(lines: int = Query(default=200, ge=1, le=2000)) -> dict[str, object]:
    try:
        config = load_config()
    except ConfigLoadError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if not config.server.log_file:
        return {"source": "not_configured", "lines": []}
    if not config.server.log_file.exists():
        return {"source": str(config.server.log_file), "lines": []}
    return {"source": str(config.server.log_file), "lines": tail_lines(config.server.log_file, lines)}


@router.get("/audit")
def audit_logs(limit: int = Query(default=200, ge=1, le=1000)) -> dict[str, object]:
    try:
        config = load_config()
    except ConfigLoadError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"events": list_audit_events(config, limit)}


def tail_lines(path, limit: int) -> list[str]:
    return path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]
