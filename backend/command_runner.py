from __future__ import annotations

import os
import re
import signal
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
    ca_password: str = "",
    timeout_seconds: int = 600,
) -> CommandResult:
    if not command:
        raise CommandError("Command is not configured")
    if not is_safe_common_name(common_name):
        raise CommandError("Invalid common name")

    replacements = {
        "{common_name}": common_name,
        "{reason}": reason,
        "{password}": password,
        "{ca_password}": ca_password,
    }
    argv = [replace_tokens(part, replacements) for part in command]
    try:
        process = subprocess.Popen(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            encoding="utf-8",
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()
            raise CommandError(f"Command timed out after {timeout_seconds} seconds")
    except OSError as exc:
        raise CommandError("Unable to execute configured command") from exc

    for secret in sorted({password, ca_password} - {""}, key=len, reverse=True):
        stdout = stdout.replace(secret, "[REDACTED]")
        stderr = stderr.replace(secret, "[REDACTED]")
    result = CommandResult(process.returncode, stdout, stderr)
    if process.returncode != 0:
        raise CommandError(result.stderr or result.stdout or f"Command exited {result.returncode}")
    return result


def replace_tokens(value: str, replacements: dict[str, str]) -> str:
    return re.sub(
        r"\{(?:common_name|reason|password|ca_password)\}",
        lambda match: replacements[match.group()], value,
    )
