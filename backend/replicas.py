from __future__ import annotations

import json
import subprocess
from dataclasses import asdict
from typing import Optional

from backend.config import OpenVPNUIConfig, ReplicaConfig
from backend.openvpn_management import (
    OpenVPNConnection,
    OpenVPNManagementClient,
    OpenVPNManagementError,
    parse_status_file,
    parse_status_text,
)


class ReplicaError(RuntimeError):
    pass


def configured_replicas(config: OpenVPNUIConfig) -> list[ReplicaConfig]:
    if config.replicas:
        return config.replicas
    if config.server.management_host and config.server.management_port:
        return [
            ReplicaConfig(
                name="local",
                role="local",
                status_file=config.server.status_file,
                management_host=config.server.management_host,
                management_port=config.server.management_port,
                management_password_file=config.server.management_password_file,
            )
        ]
    return []


def replica_statuses(config: OpenVPNUIConfig) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for replica in configured_replicas(config):
        try:
            connections = get_replica_connections(replica)
            rows.append(
                {
                    "name": replica.name,
                    "role": replica.role,
                    "status": "ok",
                    "error": "",
                    "connections": [asdict(item) for item in connections],
                }
            )
        except (OpenVPNManagementError, ReplicaError) as exc:
            rows.append(
                {
                    "name": replica.name,
                    "role": replica.role,
                    "status": "error",
                    "error": str(exc),
                    "connections": [],
                }
            )
    return rows


def get_replica_connections(replica: ReplicaConfig) -> list[OpenVPNConnection]:
    if replica.management_host and replica.management_port:
        try:
            if replica.role == "local":
                return local_client(replica).status()
            return parse_status_text(run_remote_management_command(replica, "status 2"))
        except (OpenVPNManagementError, ReplicaError):
            if not replica.status_file:
                raise

    if replica.status_file:
        if replica.role == "local":
            return parse_status_file(replica.status_file)
        return parse_status_text(remote_cat(replica, str(replica.status_file)))

    raise ReplicaError(f"Replica {replica.name} has no management endpoint or status_file")


def kill_on_replica(replica: ReplicaConfig, common_name: str) -> dict[str, str]:
    if replica.role == "local":
        return local_client(replica).kill(common_name)
    response = run_remote_management_command(replica, f"kill {common_name}")
    return {"common_name": common_name, "result": response.strip(), "node": replica.name}


def find_replica(config: OpenVPNUIConfig, name: str) -> Optional[ReplicaConfig]:
    for replica in configured_replicas(config):
        if replica.name == name:
            return replica
    return None


def local_client(replica: ReplicaConfig) -> OpenVPNManagementClient:
    if not replica.management_host or not replica.management_port:
        raise ReplicaError(f"Replica {replica.name} is missing management endpoint")
    password = None
    if replica.management_password_file:
        password = replica.management_password_file.read_text(encoding="utf-8").strip()
    return OpenVPNManagementClient(
        replica.management_host,
        replica.management_port,
        password=password,
    )


def run_remote_management_command(replica: ReplicaConfig, command: str) -> str:
    if not replica.ssh_host:
        raise ReplicaError(f"Replica {replica.name} is missing ssh_host")

    password = ""
    if replica.management_password_file:
        password = remote_cat(replica, str(replica.management_password_file)).strip()

    script = REMOTE_MANAGEMENT_SCRIPT
    payload = json.dumps(
        {
            "host": replica.management_host,
            "port": replica.management_port,
            "password": password,
            "command": command,
        }
    )
    completed = run_ssh(replica, ["python3", "-", payload], input_text=script)
    if completed.returncode != 0:
        raise ReplicaError(completed.stderr or completed.stdout or "remote management command failed")
    return completed.stdout


def remote_cat(replica: ReplicaConfig, path: str) -> str:
    completed = run_ssh(replica, ["cat", path])
    if completed.returncode != 0:
        raise ReplicaError(completed.stderr or completed.stdout or f"cannot read remote file {path}")
    return completed.stdout


def run_ssh(
    replica: ReplicaConfig,
    remote_command: list[str],
    input_text: Optional[str] = None,
) -> subprocess.CompletedProcess[str]:
    destination = f"{replica.ssh_user}@{replica.ssh_host}"
    argv = [
        "ssh",
        "-p",
        str(replica.ssh_port),
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={replica.ssh_connect_timeout}",
        destination,
        *remote_command,
    ]
    return subprocess.run(
        argv,
        input=input_text,
        capture_output=True,
        encoding="utf-8",
        timeout=replica.ssh_connect_timeout + 15,
        check=False,
    )


REMOTE_MANAGEMENT_SCRIPT = r"""
import json
import socket
import sys

payload = json.loads(sys.argv[1])

def read_until(sock):
    chunks = []
    while True:
        try:
            data = sock.recv(4096)
        except socket.timeout:
            if chunks:
                break
            raise
        if not data:
            break
        text = data.decode("utf-8", errors="replace")
        chunks.append(text)
        joined = "".join(chunks)
        stripped = joined.strip()
        if stripped.endswith("END") or "SUCCESS:" in joined or "ERROR:" in joined:
            break
        if "ENTER PASSWORD:" in joined.upper():
            break
        if stripped.endswith(">"):
            break
    return "".join(chunks)

with socket.create_connection((payload["host"], int(payload["port"])), timeout=5) as sock:
    sock.settimeout(5)
    greeting = read_until(sock)
    if "PASSWORD" in greeting.upper():
        if not payload.get("password"):
            raise RuntimeError("management password is required")
        sock.sendall(payload["password"].encode("utf-8") + b"\n")
        read_until(sock)
    sock.sendall(payload["command"].encode("utf-8") + b"\n")
    sys.stdout.write(read_until(sock))
    sock.sendall(b"quit\n")
"""
