from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from backend.config import OpenVPNUIConfig
from backend.database import get_disabled_users
from backend.openvpn_management import is_safe_common_name


@dataclass(frozen=True)
class VPNUser:
    common_name: str
    status: str
    certificate_path: str = ""
    profile_path: str = ""
    expires_at: str = ""
    revoked_at: str = ""
    serial: str = ""
    source: str = ""


def list_users(config: OpenVPNUIConfig) -> list[dict[str, str]]:
    users: dict[str, VPNUser] = {}
    index_path = config.certificates.ca_dir / "index.txt"
    if index_path.exists():
        users.update(parse_easy_rsa_index(index_path))

    if config.certificates.issued_dir.exists():
        for cert_path in sorted(config.certificates.issued_dir.glob("*.crt")):
            common_name = cert_path.stem
            if not is_safe_common_name(common_name):
                continue
            existing = users.get(common_name)
            users[common_name] = VPNUser(
                common_name=common_name,
                status=existing.status if existing else "active",
                certificate_path=str(cert_path),
                profile_path=find_profile(config.certificates.client_profiles_dir, common_name),
                expires_at=existing.expires_at if existing else "",
                revoked_at=existing.revoked_at if existing else "",
                serial=existing.serial if existing else "",
                source="index+issued" if existing else "issued",
            )

    disabled_users = get_disabled_users(config)
    result: list[VPNUser] = []
    for user in users.values():
        if user.common_name in disabled_users and user.status == "active":
            result.append(
                VPNUser(
                    common_name=user.common_name,
                    status="disabled",
                    certificate_path=user.certificate_path,
                    profile_path=user.profile_path,
                    expires_at=user.expires_at,
                    revoked_at=user.revoked_at,
                    serial=user.serial,
                    source=user.source,
                )
            )
        else:
            result.append(user)

    return [asdict(user) for user in sorted(result, key=lambda item: item.common_name.lower())]


def parse_easy_rsa_index(path: Path) -> dict[str, VPNUser]:
    users: dict[str, VPNUser] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parsed = parse_index_line(line)
        if parsed:
            users[parsed.common_name] = parsed
    return users


def parse_index_line(line: str) -> Optional[VPNUser]:
    parts = line.split("\t")
    if len(parts) < 5:
        return None

    state = parts[0]
    expires_at = parts[1] if len(parts) > 1 else ""
    revoked_at = parts[2] if len(parts) > 2 else ""
    serial = parts[3] if len(parts) > 3 else ""
    subject = parts[-1]
    common_name = extract_common_name(subject)
    if not common_name or not is_safe_common_name(common_name):
        return None

    status = {
        "V": "active",
        "R": "revoked",
        "E": "expired",
    }.get(state, "unknown")

    return VPNUser(
        common_name=common_name,
        status=status,
        expires_at=expires_at,
        revoked_at=revoked_at,
        serial=serial,
        source="index",
    )


def extract_common_name(subject: str) -> str:
    for part in subject.split("/"):
        if part.startswith("CN="):
            return part.removeprefix("CN=")
    return ""


def find_profile(profile_dir: Path, common_name: str) -> str:
    for suffix in (".ovpn", ".conf"):
        candidate = profile_dir / f"{common_name}{suffix}"
        if candidate.exists():
            return str(candidate)
    return ""
