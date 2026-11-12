from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import importlib.util
import json
import time

import pyotp
import pytest
from fastapi.testclient import TestClient

from backend.config import OpenVPNUIConfig
from backend.otp_store import OTPError, OTPStore, initialize


@pytest.fixture
def store(tmp_path):
    ca = tmp_path / "pki"
    ca.mkdir()
    (ca / "issued").mkdir()
    (ca / "index.txt").write_text(
        "V\t350101000000Z\t\t01\tunknown\t/CN=alice\n"
        "V\t350101000000Z\t\t02\tunknown\t/CN=bob\n"
        "R\t350101000000Z\t250101000000Z\t03\tunknown\t/CN=revoked\n"
    )
    config = OpenVPNUIConfig.model_validate({
        "app": {"database_url": "sqlite:///" + str(tmp_path / "panel.db")},
        "server": {"config_path": "/not-touched/server.conf", "service_name": "openvpn.service"},
        "certificates": {"ca_dir": ca, "issued_dir": ca / "issued", "private_dir": ca,
                         "crl_path": ca / "crl.pem", "client_profiles_dir": tmp_path},
        "otp": {"enabled": True, "data_dir": tmp_path / "otp"},
    })
    initialize(config)
    return OTPStore(config)


def bind(store, name="alice"):
    enrollment = store.enroll(name, "")
    assert enrollment["qr"].startswith("data:image/png;base64,")
    with store.connect() as db:
        encrypted = db.execute("SELECT pending FROM users WHERE name=?", (name,)).fetchone()[0]
    secret = store.cipher.decrypt(encrypted.encode()).decode()
    now = int(time.time())
    store.confirm(name, pyotp.TOTP(secret).at(now))
    return secret, now


def test_default_and_off_policy_still_checks_identity(store):
    assert store.status()["enforced"] is False
    assert store.verify("vpn-1", "alice", "alice", "anything")
    assert not store.verify("vpn-1", "alice", "bob", "anything")
    assert not store.verify("vpn-1", "revoked", "revoked", "anything")
    assert not store.verify("vpn-1", "missing", "missing", "anything")
    assert not Path("/not-touched/server.conf").exists()


def test_required_otp_binding_and_atomic_cross_node_replay(store, monkeypatch):
    secret, now = bind(store)
    store.set_enforced(True)
    assert not store.verify("vpn-1", "bob", "bob", "123456")
    # Confirmation consumes its code too. Use the next time step for the login test.
    monkeypatch.setattr("backend.otp_store.time.time", lambda: now + 30)
    code = pyotp.TOTP(secret).at(now + 30)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda node: OTPStore(store.config).verify(node, "alice", "alice", code),
                                ["vpn-1", "vpn-2"]))
    assert sorted(results) == [False, True]
    assert not store.verify("vpn-1", "alice", "alice", code)
    assert store.status()["enforced"] is True
    assert OTPStore(store.config).status()["enforced"] is True
    with store.connect() as db:
        text = " ".join(str(tuple(r)) for r in db.execute("SELECT * FROM events"))
        encrypted = db.execute("SELECT secret FROM users WHERE name='alice'").fetchone()[0]
    assert secret not in encrypted and secret not in text and code not in text


def test_reset_preserves_active_secret_until_confirmed_and_cancel(store):
    bind(store)
    with store.connect() as db:
        old = db.execute("SELECT secret FROM users WHERE name='alice'").fetchone()[0]
    with pytest.raises(OTPError):
        store.enroll("alice", "wrong")
    store.enroll("alice", "alice")
    with store.connect() as db:
        assert db.execute("SELECT secret FROM users WHERE name='alice'").fetchone()[0] == old
    store.cancel("alice")
    assert store.status()["users"]["alice"] == {"bound": True, "pending": False}
    with pytest.raises(OTPError):
        store.enroll("revoked", "")


def test_failed_confirmation_is_rate_limited_and_expired(store):
    store.enroll("alice", "")
    for _ in range(5):
        with pytest.raises(OTPError):
            store.confirm("alice", "bad")
    with pytest.raises(OTPError, match="Too many"):
        store.confirm("alice", "123456")
    with store.connect() as db:
        db.execute("UPDATE users SET pending_until=0 WHERE name='alice'")
    with pytest.raises(OTPError, match="expired"):
        store.confirm("alice", "123456")


def test_otp_rate_limit_and_disabled_user(store, monkeypatch):
    from backend.database import set_user_disabled
    secret, now = bind(store)
    store.set_enforced(True)
    for _ in range(5):
        assert not store.verify("vpn-1", "alice", "alice", "bad")
    monkeypatch.setattr("backend.otp_store.time.time", lambda: now + 30)
    assert not store.verify("vpn-2", "alice", "alice", pyotp.TOTP(secret).at(now + 30))
    monkeypatch.setattr("backend.otp_store.time.time", lambda: now + 90)
    assert store.verify("vpn-2", "alice", "alice", pyotp.TOTP(secret).at(now + 90))
    set_user_disabled(store.config, "alice", True)
    store.set_enforced(False)
    assert not store.verify("vpn-1", "alice", "alice", "ignored")


def test_admin_and_node_credentials_and_separate_service(store, monkeypatch):
    from backend.main import create_app
    from backend import otp_service
    from backend.routers import otp
    monkeypatch.setattr(otp, "load_config", lambda: store.config)
    monkeypatch.setattr(otp_service, "load_config", lambda: store.config)
    with TestClient(create_app()) as panel, TestClient(otp_service.app) as verifier:
        assert panel.get("/api/otp").status_code == 401
        admin = {"Authorization": "Bearer " + store.admin_token}
        assert panel.get("/api/otp", headers=admin).headers["cache-control"] == "no-store"
        assert panel.post("/api/otp/policy", headers=admin, json={"enforced": True, "confirmation": "no"}).status_code == 400
        assert panel.post("/api/otp/policy", headers=admin, json={"enforced": True, "confirmation": "ENABLE"}).status_code == 200
        payload = {"node": "vpn-1", "common_name": "alice", "username": "alice", "code": "123456"}
        assert verifier.post("/verify", json=payload).status_code == 401
        assert verifier.post("/verify", headers=admin, json=payload).status_code == 401
        node = {"Authorization": "Bearer " + store.node_tokens["vpn-1"]}
        assert panel.get("/api/otp", headers=node).status_code == 401
        assert verifier.post("/verify", headers=node, json=payload).json() == {"allowed": False}
        payload["node"] = "vpn-2"
        assert verifier.post("/verify", headers=node, json=payload).status_code == 401
        assert verifier.get("/health").status_code == 200
        store.set_enforced(False)
        payload["node"] = "vpn-1"
        assert verifier.post("/verify", headers=node, json=payload).json() == {"allowed": True}


def test_private_credentials_and_no_reinitialization(store):
    with pytest.raises(OTPError):
        initialize(store.config)
    token = store.root / "admin.token"
    token.chmod(0o644)
    with pytest.raises(OTPError):
        OTPStore(store.config)


def test_hook_fails_closed_and_rejects_lan_http(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("hook", "scripts/otp-verify.py")
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)
    config = tmp_path / "node.json"
    creds = tmp_path / "credentials"
    creds.write_text("alice\n123456\n")
    config.write_text(json.dumps({"url": "http://192.168.0.77:8001/verify"}))
    assert not hook.verify(str(config), str(creds))
    monkeypatch.setenv("common_name", "bob")
    token = tmp_path / "token"
    token.write_text("x" * 64)
    config.write_text(json.dumps({"url": "http://127.0.0.1:1/verify", "node": "vpn-1", "token_file": str(token)}))
    assert not hook.verify(str(config), str(creds))
    monkeypatch.setenv("common_name", "alice")
    with pytest.raises(Exception):
        hook.verify(str(config), str(creds))


def test_hook_payload_transport_and_exact_allow_response(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("hook", "scripts/otp-verify.py")
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)
    monkeypatch.setenv("common_name", "alice")
    token = tmp_path / "token"
    token.write_text("x" * 64)
    credentials = tmp_path / "credentials"
    credentials.write_text("alice\n123456\n")
    config = tmp_path / "node.json"
    config.write_text(json.dumps({"url": "http://127.0.0.1:8001/verify", "node": "vpn-2", "token_file": str(token)}))
    response_body = {"allowed": True}

    class Reply:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, limit):
            return json.dumps(response_body).encode()

    class Opener:
        def open(self, request, timeout):
            assert timeout == 5
            assert request.get_header("Authorization") == "Bearer " + "x" * 64
            assert json.loads(request.data) == {"node": "vpn-2", "common_name": "alice", "username": "alice", "code": "123456"}
            return Reply()

    monkeypatch.setattr(hook, "build_opener", lambda *args: Opener())
    assert hook.verify(str(config), str(credentials))
    response_body["allowed"] = "true"
    assert not hook.verify(str(config), str(credentials))
    assert hook.NoRedirect().redirect_request(None, None, 302, "", {}, "http://example.com") is None


def test_feature_disabled_and_missing_store_do_not_affect_original_routes(store, monkeypatch):
    from backend.main import create_app
    from backend.routers import otp
    disabled = store.config.model_copy(update={"otp": store.config.otp.model_copy(update={"enabled": False})})
    monkeypatch.setattr(otp, "load_config", lambda: disabled)
    with TestClient(create_app()) as panel:
        assert panel.get("/api/otp").status_code == 503
    with pytest.raises(OTPError, match="disabled"):
        OTPStore(disabled)
    store.root.joinpath("encryption.key").unlink()
    with pytest.raises(OTPError):
        OTPStore(store.config)
