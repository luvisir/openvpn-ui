from dataclasses import asdict

from fastapi import APIRouter, HTTPException

from backend.config import ConfigLoadError, load_config
from backend.database import add_audit_event
from backend.openvpn_management import (
    OpenVPNManagementError,
    create_management_client,
    parse_status_file,
)
from backend.replicas import ReplicaError, find_replica, kill_on_replica, replica_statuses

router = APIRouter()


@router.get("")
def list_connections() -> dict[str, object]:
    try:
        config = load_config()
    except ConfigLoadError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    nodes = replica_statuses(config)
    if nodes:
        flattened = []
        for node in nodes:
            for connection in node["connections"]:
                flattened.append({**connection, "node": node["name"]})
        return {"source": "replicas", "nodes": nodes, "connections": flattened}

    management_client = create_management_client(config)
    if management_client:
        try:
            connections = management_client.status()
            return {
                "source": "management",
                "nodes": [
                    {
                        "name": "local",
                        "role": "local",
                        "status": "ok",
                        "error": "",
                        "connections": [asdict(item) for item in connections],
                    }
                ],
                "connections": [asdict(item) for item in connections],
            }
        except OpenVPNManagementError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    if config.server.status_file and config.server.status_file.exists():
        connections = parse_status_file(config.server.status_file)
        return {"source": "status_file", "nodes": [], "connections": [asdict(item) for item in connections]}

    return {"source": "none", "nodes": [], "connections": []}


@router.post("/{common_name}/kick")
def kick_connection(common_name: str, node: str = "") -> dict[str, object]:
    try:
        config = load_config()
    except ConfigLoadError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if not config.features.allow_kick_user:
        raise HTTPException(status_code=403, detail="Kick user feature is disabled")

    if node:
        replica = find_replica(config, node)
        if not replica:
            raise HTTPException(status_code=404, detail="Replica not found")
        try:
            result = kill_on_replica(replica, common_name)
            add_audit_event(config, "user.kicked", f"{node}:{common_name}")
            return result
        except (OpenVPNManagementError, ReplicaError) as exc:
            add_audit_event(
                config, "user.kicked", f"{node}:{common_name}", result="failed", error=str(exc)
            )
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    management_client = create_management_client(config)
    if not management_client:
        raise HTTPException(status_code=409, detail="OpenVPN management interface is not configured")

    try:
        result = management_client.kill(common_name)
        add_audit_event(config, "user.kicked", common_name)
        return result
    except OpenVPNManagementError as exc:
        add_audit_event(config, "user.kicked", common_name, result="failed", error=str(exc))
        raise HTTPException(status_code=503, detail=str(exc)) from exc
