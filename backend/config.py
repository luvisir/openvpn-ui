from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


DEFAULT_CONFIG_PATH = Path("config/openvpn-ui.yaml")
CONFIG_ENV_VAR = "OPENVPN_UI_CONFIG"


class AppConfig(BaseModel):
    name: str = "OpenVPN UI"
    environment: Literal["development", "staging", "production"] = "development"
    database_url: str = "sqlite:///./openvpn-ui.db"


class ServerConfig(BaseModel):
    config_path: Path
    service_name: str
    status_file: Optional[Path] = None
    log_file: Optional[Path] = None
    management_host: Optional[str] = None
    management_port: Optional[int] = Field(default=None, ge=1, le=65535)
    management_password_file: Optional[Path] = None


class CertificateConfig(BaseModel):
    ca_dir: Path
    easy_rsa_dir: Optional[Path] = None
    issued_dir: Path
    private_dir: Path
    crl_path: Path
    client_profiles_dir: Path


class LifecycleConfig(BaseModel):
    client_config_dir: Optional[Path] = None
    create_user_command: list[str] = Field(default_factory=list)
    generate_profile_command: list[str] = Field(default_factory=list)
    disable_user_command: list[str] = Field(default_factory=list)
    enable_user_command: list[str] = Field(default_factory=list)
    revoke_user_command: list[str] = Field(default_factory=list)
    reload_command: list[str] = Field(default_factory=list)

    @field_validator(
        "create_user_command",
        "generate_profile_command",
        "disable_user_command",
        "enable_user_command",
        "revoke_user_command",
        "reload_command",
    )
    @classmethod
    def command_must_be_argv(cls, value: list[str]) -> list[str]:
        if any(not item or item.strip() != item for item in value):
            raise ValueError("commands must be argv arrays with non-empty, trimmed items")
        return value


class ReplicaConfig(BaseModel):
    name: str
    role: Literal["local", "ssh"] = "local"
    management_host: str = "127.0.0.1"
    management_port: int = Field(default=7505, ge=1, le=65535)
    management_password_file: Optional[Path] = None
    ssh_host: Optional[str] = None
    ssh_user: str = "root"
    ssh_port: int = Field(default=22, ge=1, le=65535)
    ssh_connect_timeout: int = Field(default=5, ge=1, le=60)


class FeatureConfig(BaseModel):
    allow_create_user: bool = False
    allow_disable_user: bool = False
    allow_kick_user: bool = False
    allow_revoke_user: bool = False
    allow_openvpn_reload: bool = False


class OpenVPNUIConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app: AppConfig
    server: ServerConfig
    certificates: CertificateConfig
    lifecycle: LifecycleConfig = Field(default_factory=LifecycleConfig)
    replicas: list[ReplicaConfig] = Field(default_factory=list)
    features: FeatureConfig = Field(default_factory=FeatureConfig)

    def sanitized(self) -> dict[str, Any]:
        return {
            "app": self.app.model_dump(),
            "server": {
                "config_path": str(self.server.config_path),
                "service_name": self.server.service_name,
                "status_file": str(self.server.status_file) if self.server.status_file else None,
                "log_file": str(self.server.log_file) if self.server.log_file else None,
                "management_enabled": bool(
                    self.server.management_host and self.server.management_port
                ),
                "management_auth_configured": bool(self.server.management_password_file),
            },
            "certificates": {
                "ca_dir": str(self.certificates.ca_dir),
                "easy_rsa_dir": (
                    str(self.certificates.easy_rsa_dir)
                    if self.certificates.easy_rsa_dir
                    else None
                ),
                "issued_dir": str(self.certificates.issued_dir),
                "private_dir": str(self.certificates.private_dir),
                "crl_path": str(self.certificates.crl_path),
                "client_profiles_dir": str(self.certificates.client_profiles_dir),
            },
            "lifecycle": {
                "client_config_dir": (
                    str(self.lifecycle.client_config_dir)
                    if self.lifecycle.client_config_dir
                    else None
                ),
                "create_user_configured": bool(self.lifecycle.create_user_command),
                "generate_profile_configured": bool(self.lifecycle.generate_profile_command),
                "disable_user_configured": bool(self.lifecycle.disable_user_command),
                "enable_user_configured": bool(self.lifecycle.enable_user_command),
                "revoke_user_configured": bool(self.lifecycle.revoke_user_command),
                "reload_configured": bool(self.lifecycle.reload_command),
            },
            "replicas": [
                {
                    "name": replica.name,
                    "role": replica.role,
                    "management_host": replica.management_host,
                    "management_port": replica.management_port,
                    "management_auth_configured": bool(replica.management_password_file),
                    "ssh_host": replica.ssh_host,
                    "ssh_user": replica.ssh_user if replica.role == "ssh" else None,
                    "ssh_port": replica.ssh_port if replica.role == "ssh" else None,
                }
                for replica in self.replicas
            ],
            "features": self.features.model_dump(),
        }


class ConfigLoadError(RuntimeError):
    pass


def get_config_path() -> Path:
    return Path(os.environ.get(CONFIG_ENV_VAR, DEFAULT_CONFIG_PATH))


def load_config(path: Optional[Path] = None) -> OpenVPNUIConfig:
    if path is None:
        return _load_config_cached(str(get_config_path()))
    return _load_config(path)


@lru_cache(maxsize=1)
def _load_config_cached(path: str) -> OpenVPNUIConfig:
    return _load_config(Path(path))


def _load_config(config_path: Path) -> OpenVPNUIConfig:
    if not config_path.exists():
        raise ConfigLoadError(
            f"Config file not found: {config_path}. "
            "Copy config/openvpn-ui.example.yaml and set OPENVPN_UI_CONFIG if needed."
        )

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        return OpenVPNUIConfig.model_validate(raw)
    except yaml.YAMLError as exc:
        raise ConfigLoadError(f"Invalid YAML in {config_path}: {exc}") from exc
    except ValidationError as exc:
        raise ConfigLoadError(f"Invalid config in {config_path}: {exc}") from exc


def validate_config_paths(config: OpenVPNUIConfig) -> list[dict[str, str]]:
    checks: list[tuple[str, Optional[Path], str]] = [
        ("server.config_path", config.server.config_path, "file"),
        ("server.status_file", config.server.status_file, "file"),
        ("server.log_file", config.server.log_file, "file"),
        ("server.management_password_file", config.server.management_password_file, "file"),
        ("certificates.ca_dir", config.certificates.ca_dir, "dir"),
        ("certificates.easy_rsa_dir", config.certificates.easy_rsa_dir, "dir"),
        ("certificates.issued_dir", config.certificates.issued_dir, "dir"),
        ("certificates.private_dir", config.certificates.private_dir, "dir"),
        ("certificates.crl_path", config.certificates.crl_path, "file"),
        ("certificates.client_profiles_dir", config.certificates.client_profiles_dir, "dir"),
        ("lifecycle.client_config_dir", config.lifecycle.client_config_dir, "dir"),
    ]

    results: list[dict[str, str]] = []
    for name, path, expected in checks:
        if path is None:
            results.append({"name": name, "status": "not_configured", "path": ""})
            continue
        exists = path.exists()
        type_ok = path.is_dir() if expected == "dir" else path.is_file()
        status = "ok" if exists and type_ok else "missing" if not exists else "wrong_type"
        results.append({"name": name, "status": status, "path": str(path)})
    return results
