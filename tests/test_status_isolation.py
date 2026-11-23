from pathlib import Path
from unittest.mock import patch

import pytest

from backend.config import FeatureConfig, ReplicaConfig
from backend.replicas import get_replica_connections


@pytest.mark.parametrize("role", ["local", "ssh"])
@pytest.mark.parametrize("has_file", [True, False])
def test_default_status_never_connects_management(role, has_file):
    replica = ReplicaConfig(
        name="test", role=role, ssh_host="example.invalid",
        status_file=Path("/missing-status") if has_file else None,
        management_host="127.0.0.1", management_port=7505,
    )
    with patch("backend.replicas.local_client") as local, patch(
        "backend.replicas.run_remote_management_command"
    ) as remote, patch("backend.replicas.remote_cat", side_effect=OSError("missing")):
        with pytest.raises((OSError, RuntimeError)):
            get_replica_connections(replica)
        local.assert_not_called()
        remote.assert_not_called()


def test_status_file_still_works_without_management(tmp_path):
    status = tmp_path / "status.log"
    status.write_text("OpenVPN CLIENT LIST\nCommon Name,Real Address,Bytes Received,Bytes Sent,Connected Since\nalice,192.0.2.1:1000,10,20,today\nEND\n")
    replica = ReplicaConfig(name="local", status_file=status)
    assert get_replica_connections(replica)[0].common_name == "alice"
    assert FeatureConfig().allow_management_status is False


def test_connections_endpoint_never_opens_management_by_default():
    from fastapi.testclient import TestClient
    from backend.config import load_config
    from backend.main import create_app

    config = load_config(Path("config/openvpn-ui.example.yaml"))
    with patch("backend.routers.connections.load_config", return_value=config), patch(
        "backend.routers.connections.replica_statuses", return_value=[]
    ), patch("backend.routers.connections.create_management_client") as client:
        with TestClient(create_app()) as app:
            assert app.get("/api/connections").status_code == 200
        client.assert_not_called()
