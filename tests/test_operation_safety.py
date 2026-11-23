import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from backend.command_runner import CommandError, replace_tokens, run_configured_command
from backend.config import FeatureConfig, load_config
from backend.openvpn_management import OpenVPNManagementClient, OpenVPNManagementError, is_safe_common_name, parse_status_text
from backend.replicas import ReplicaConfig, ReplicaError, kill_on_replica, run_ssh


@pytest.mark.parametrize("name", [".", "..", "--help", "alice\nsignal SIGTERM", "alice\rkill bob", "../alice", "用户"])
def test_names_rejected_before_remote_access(name):
    assert not is_safe_common_name(name)
    with patch("backend.replicas.run_remote_management_command") as remote:
        with pytest.raises(ReplicaError):
            kill_on_replica(ReplicaConfig(name="two", role="ssh"), name)
        remote.assert_not_called()


@pytest.mark.parametrize("script", list(Path("scripts").glob("ui-*-user.sh")))
@pytest.mark.parametrize("name", [".", "..", "--help"])
def test_shell_rejects_unsafe_names_before_any_changes(script, name):
    result = subprocess.run(["bash", str(script), name], capture_output=True)
    assert result.returncode == 2


def test_kick_errors_not_reported_as_success():
    client = OpenVPNManagementClient("localhost", 1)
    with patch.object(client, "_command", return_value="ERROR: client not found"):
        with pytest.raises(OpenVPNManagementError):
            client.kill("alice")
    with patch("backend.replicas.run_remote_management_command", return_value="ERROR: client not found"):
        with pytest.raises(ReplicaError):
            kill_on_replica(ReplicaConfig(name="two", role="ssh"), "alice")


def test_ssh_timeout_is_controlled_error():
    with patch("backend.replicas.subprocess.run", side_effect=subprocess.TimeoutExpired("ssh", 5)):
        with pytest.raises(ReplicaError):
            run_ssh(ReplicaConfig(name="two", ssh_host="example.invalid"), ["cat", "/file"])


def test_credentials_are_literal_and_redacted():
    assert replace_tokens("{password}", {"{password}": "{ca_password}", "{ca_password}": "CA"}) == "{ca_password}"
    result = run_configured_command([sys.executable, "-c", "import sys; print(sys.argv[1]); print(sys.argv[2],file=sys.stderr)", "{password}", "{ca_password}"], "alice", password="private-pass", ca_password="ca-pass")
    assert result.stdout == "[REDACTED]\n" and result.stderr == "[REDACTED]\n"
    with pytest.raises(CommandError) as error:
        run_configured_command([sys.executable, "-c", "import sys; print(sys.argv[1],file=sys.stderr); sys.exit(1)", "{password}"], "alice", password="private-pass")
    assert "private-pass" not in str(error.value)


def test_timeout_stops_child_before_it_can_modify_files(tmp_path):
    marker = tmp_path / "late-change"
    child = "import time; from pathlib import Path; time.sleep(0.6); Path(%r).touch()" % str(marker)
    parent = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',sys.argv[1]]); time.sleep(10)"
    with pytest.raises(CommandError, match="timed out"):
        run_configured_command([sys.executable, "-c", parent, child], "alice", timeout_seconds=0.2)
    time.sleep(0.8)
    assert not marker.exists()


@pytest.mark.parametrize("action", ["disable", "enable"])
def test_unconfigured_lifecycle_cannot_change_database(action):
    from backend.routers import users
    config = load_config(Path("config/openvpn-ui.example.yaml"))
    config.features = FeatureConfig(allow_disable_user=True)
    config.lifecycle.disable_user_command = []
    config.lifecycle.enable_user_command = []
    with patch.object(users, "_load", return_value=config), patch.object(users, "set_user_disabled") as change:
        with pytest.raises(HTTPException) as error:
            getattr(users, action + "_user")("alice", users.UserActionRequest())
        assert error.value.status_code == 409
        change.assert_not_called()


def test_duplicate_cn_classic_status_preserves_both_sessions():
    text = "OpenVPN CLIENT LIST\nalice,192.0.2.1:1,10,20,today\nalice,192.0.2.2:2,30,40,today\nROUTING TABLE\n10.8.0.6,alice,192.0.2.1:1,today\n10.8.0.10,alice,192.0.2.2:2,today\nEND\n"
    rows = parse_status_text(text)
    assert [r.virtual_address for r in rows] == ["10.8.0.6", "10.8.0.10"]


def test_tab_separated_status_v3():
    text = "HEADER\tCLIENT_LIST\tCommon Name\tReal Address\tVirtual Address\tBytes Received\tBytes Sent\nCLIENT_LIST\talice\t192.0.2.1:1\t10.8.0.6\t10\t20\nEND\n"
    assert parse_status_text(text)[0].bytes_sent == 20


def test_duplicate_creation_never_runs_signing_command():
    from backend.routers import users
    config = load_config(Path("config/openvpn-ui.example.yaml"))
    config.features.allow_create_user = True
    with patch.object(users, "_load", return_value=config), patch.object(
        users, "list_users", return_value=[{"common_name": "alice"}]
    ), patch.object(users, "run_configured_command") as command:
        with pytest.raises(HTTPException) as error:
            users.create_user(users.CreateUserRequest(common_name="alice", password="secret", ca_password="secret"))
        assert error.value.status_code == 409
        command.assert_not_called()
