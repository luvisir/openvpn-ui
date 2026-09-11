from __future__ import annotations

import socket
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from backend.config import OpenVPNUIConfig


class OpenVPNManagementError(RuntimeError):
    pass


@dataclass(frozen=True)
class OpenVPNConnection:
    common_name: str
    real_address: str
    virtual_address: str
    bytes_received: int
    bytes_sent: int
    connected_since: str
    username: str = ""
    client_id: str = ""
    peer_id: str = ""


class OpenVPNManagementClient:
    def __init__(self, host: str, port: int, password: Optional[str] = None, timeout: float = 5.0):
        self.host = host
        self.port = port
        self.password = password
        self.timeout = timeout

    def status(self) -> list[OpenVPNConnection]:
        return parse_status_text(self._command("status 2"))

    def kill(self, common_name: str) -> dict[str, str]:
        if not is_safe_common_name(common_name):
            raise OpenVPNManagementError("Invalid common name")
        response = self._command(f"kill {common_name}")
        return {"common_name": common_name, "result": response.strip()}

    def _command(self, command: str) -> str:
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
                sock.settimeout(self.timeout)
                greeting = self._read_until_prompt(sock)
                if "PASSWORD" in greeting.upper():
                    if self.password is None:
                        raise OpenVPNManagementError("Management password is required")
                    self._send_line(sock, self.password)
                    self._read_until_prompt(sock)

                self._send_line(sock, command)
                response = self._read_until_prompt(sock)
                self._send_line(sock, "quit")
                return response
        except (OSError, socket.timeout) as exc:
            raise OpenVPNManagementError(
                f"Cannot connect to OpenVPN management interface {self.host}:{self.port}: {exc}"
            ) from exc

    def _send_line(self, sock: socket.socket, value: str) -> None:
        sock.sendall(value.encode("utf-8") + b"\n")

    def _read_until_prompt(self, sock: socket.socket) -> str:
        chunks: list[str] = []
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
            if joined.startswith(">INFO:") and joined.endswith(("\n", "\r\n")):
                break
            if stripped.endswith(">"):
                break
        return "".join(chunks)


def create_management_client(config: OpenVPNUIConfig) -> Optional[OpenVPNManagementClient]:
    if not config.server.management_host or not config.server.management_port:
        return None

    password = None
    if config.server.management_password_file:
        password = config.server.management_password_file.read_text(encoding="utf-8").strip()

    return OpenVPNManagementClient(
        config.server.management_host,
        config.server.management_port,
        password=password,
    )


def parse_status_file(path: Path) -> list[OpenVPNConnection]:
    return parse_status_text(path.read_text(encoding="utf-8", errors="replace"))


def parse_status_text(text: str) -> list[OpenVPNConnection]:
    rows: list[OpenVPNConnection] = []
    for line in text.splitlines():
        if line.startswith("CLIENT_LIST,"):
            rows.append(parse_client_list_csv(line.split(",")))
    return rows


def parse_client_list_csv(parts: list[str]) -> OpenVPNConnection:
    def str_at(index: int) -> str:
        try:
            return parts[index]
        except IndexError:
            return ""

    def int_at(index: int) -> int:
        try:
            return int(parts[index])
        except (IndexError, ValueError):
            return 0

    return OpenVPNConnection(
        common_name=str_at(1),
        real_address=str_at(2),
        virtual_address=str_at(3),
        bytes_received=int_at(4),
        bytes_sent=int_at(5),
        connected_since=normalize_connected_since(str_at(7) or str_at(6)),
        username=str_at(9),
        client_id=str_at(10),
        peer_id=str_at(11),
    )


def normalize_connected_since(value: str) -> str:
    if value.isdigit():
        return datetime.fromtimestamp(int(value)).isoformat()
    return value


def is_safe_common_name(value: str) -> bool:
    return bool(value) and len(value) <= 128 and all(
        char.isalnum() or char in {".", "-", "_", "@"} for char in value
    )
