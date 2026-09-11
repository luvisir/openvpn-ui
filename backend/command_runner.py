from __future__ import annotations

import subprocess
from dataclasses import dataclass

from backend.openvpn_management import is_safe_common_name


class CommandError(RuntimeError):
    pass


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


def run_configured_command(
    command: list[str],
    common_name: str,
    reason: str = "",
    password: str = "",
) -> CommandResult:
    if not command:
        raise CommandError("Command is not configured")
    if not is_safe_common_name(common_name):
        raise CommandError("Invalid common name")

    replacements = {
        "{common_name}": common_name,
        "{reason}": reason,
        "{password}": password,
    }
    argv = [replace_tokens(part, replacements) for part in command]
    try:
        completed = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            encoding="utf-8",
            timeout=120,
        )
    except OSError as exc:
        raise CommandError(str(exc)) from exc
    except subprocess.TimeoutExpired as exc:
        raise CommandError(f"Command timed out after {exc.timeout} seconds") from exc

    result = CommandResult(completed.returncode, completed.stdout, completed.stderr)
    if completed.returncode != 0:
        raise CommandError(result.stderr or result.stdout or f"Command exited {result.returncode}")
    return result


def replace_tokens(value: str, replacements: dict[str, str]) -> str:
    result = value
    for token, replacement in replacements.items():
        result = result.replace(token, replacement)
    return result
