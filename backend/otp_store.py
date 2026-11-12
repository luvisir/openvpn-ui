"""Shared persistent OTP state for the panel and the independent verifier process."""
from __future__ import annotations

import base64
import hmac
import io
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

import pyotp
import qrcode
from cryptography.fernet import Fernet

from backend.config import OpenVPNUIConfig
from backend.users import list_users


class OTPError(ValueError):
    pass


def secure_read(path: Path) -> str:
    if not path.is_file() or path.is_symlink() or path.stat().st_mode & 0o077:
        raise OTPError("OTP credential files must exist, be private (0600), and not be symlinks")
    value = path.read_text().strip()
    if not value:
        raise OTPError("OTP credential file is empty")
    return value


class OTPStore:
    def __init__(self, config: OpenVPNUIConfig):
        if not config.otp.enabled:
            raise OTPError("OTP module is disabled in configuration")
        self.config = config
        self.root = config.otp.data_dir
        if not self.root.is_dir() or self.root.is_symlink() or self.root.stat().st_mode & 0o077:
            raise OTPError("Initialize the OTP directory first; directory permissions must be 0700")
        self.cipher = Fernet(secure_read(self.root / "encryption.key").encode())
        self.admin_token = secure_read(self.root / "admin.token")
        self.node_tokens = {
            name: secure_read(self.root / (name + ".token")) for name in config.otp.nodes
        }
        db_path = self.root / "otp.db"
        if not db_path.is_file() or db_path.is_symlink() or db_path.stat().st_mode & 0o077:
            raise OTPError("Initialize the OTP database first; database permissions must be 0600")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.root / "otp.db", timeout=10)
        db.row_factory = sqlite3.Row
        try:
            # Serialize check-and-consume across both VPN nodes and all worker processes.
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def audit(self, db, action, target="", node="", result="success", detail=""):
        db.execute(
            "INSERT INTO events (at,action,target,node,result,detail) VALUES (?,?,?,?,?,?)",
            (int(time.time()), action, target, node, result, detail),
        )
        db.execute("DELETE FROM events WHERE id <= (SELECT COALESCE(MAX(id),0)-10000 FROM events)")

    def active_user(self, name):
        return any(u["common_name"] == name and u["status"] == "active"
                   for u in list_users(self.config))

    def status(self):
        with self.connect() as db:
            enforced = bool(db.execute("SELECT enforced FROM settings WHERE id=1").fetchone()[0])
            users = {r["name"]: {"bound": bool(r["secret"]),
                                  "pending": bool(r["pending"] and r["pending_until"] > time.time())}
                     for r in db.execute("SELECT * FROM users")}
            events = [dict(r) for r in db.execute("SELECT * FROM events ORDER BY id DESC LIMIT 100")]
        return {"enforced": enforced, "users": users, "events": events}

    def set_enforced(self, value):
        with self.connect() as db:
            db.execute("UPDATE settings SET enforced=? WHERE id=1", (int(value),))
            self.audit(db, "otp.enforcement", detail="enabled" if value else "disabled")

    def enroll(self, name, confirmation):
        if not self.active_user(name):
            raise OTPError("Only active certificate users can enroll")
        secret = pyotp.random_base32()
        with self.connect() as db:
            row = db.execute("SELECT secret FROM users WHERE name=?", (name,)).fetchone()
            if row and row[0] and confirmation != name:
                raise OTPError("Confirm the username to reset OTP")
            db.execute("INSERT OR IGNORE INTO users (name) VALUES (?)", (name,))
            db.execute("UPDATE users SET pending=?, pending_until=? WHERE name=?",
                       (self.cipher.encrypt(secret.encode()).decode(), int(time.time()) + 600, name))
            self.audit(db, "otp.enrollment.started", name)
        uri = pyotp.TOTP(secret).provisioning_uri(name=name, issuer_name=self.config.otp.issuer)
        output = io.BytesIO()
        qrcode.make(uri).save(output, format="PNG")
        return {"name": name, "qr": "data:image/png;base64," + base64.b64encode(output.getvalue()).decode(),
                "expires_in": 600}

    def cancel(self, name):
        with self.connect() as db:
            db.execute("UPDATE users SET pending=NULL,pending_until=0 WHERE name=?", (name,))
            self.audit(db, "otp.enrollment.cancelled", name)

    def confirm(self, name, code):
        if not self.active_user(name):
            raise OTPError("Only active certificate users can enroll")
        now = int(time.time())
        error = None
        with self.connect() as db:
            row = db.execute("SELECT * FROM users WHERE name=?", (name,)).fetchone()
            if not row or not row["pending"] or row["pending_until"] < now:
                error = "Enrollment expired; generate a new QR code"
            elif row["blocked_until"] > now:
                error = "Too many attempts; wait one minute"
            else:
                step = self.match(row["pending"], code, now)
                if step is None:
                    self.failure(db, name, row, now)
                    error = "Invalid verification code"
                else:
                    db.execute("UPDATE users SET secret=pending,pending=NULL,pending_until=0,"
                               "last_step=?,failures=0,blocked_until=0 WHERE name=?", (step, name))
            self.audit(db, "otp.enrollment.confirmed", name,
                       result="failed" if error else "success", detail=error or "")
        if error:
            raise OTPError(error)

    def match(self, encrypted, code, now):
        if len(code) != 6 or not code.isascii() or not code.isdigit():
            return None
        totp = pyotp.TOTP(self.cipher.decrypt(encrypted.encode()).decode())
        for step in (now // 30, now // 30 - 1, now // 30 + 1):
            if hmac.compare_digest(totp.at(step * 30), code):
                return step
        return None

    def failure(self, db, name, row, now):
        failures = row["failures"] + 1
        db.execute("UPDATE users SET failures=?,blocked_until=? WHERE name=?",
                   (0 if failures >= 5 else failures, now + 60 if failures >= 5 else 0, name))

    def verify(self, node, name, username, code):
        now = int(time.time())
        valid_user = self.active_user(name)
        with self.connect() as db:
            enforced = bool(db.execute("SELECT enforced FROM settings WHERE id=1").fetchone()[0])
            row = db.execute("SELECT * FROM users WHERE name=?", (name,)).fetchone()
            detail = ""
            if not valid_user:
                detail = "inactive or unknown certificate user"
            elif username != name:
                detail = "certificate and username mismatch"
            elif not enforced:
                detail = "OTP bypassed by administrator policy"
            elif not row or not row["secret"]:
                detail = "OTP not enrolled"
            elif row["blocked_until"] > now:
                detail = "rate limited"
            else:
                step = self.match(row["secret"], code, now)
                if step is None or step <= row["last_step"]:
                    self.failure(db, name, row, now)
                    detail = "invalid, expired or reused OTP"
                else:
                    db.execute("UPDATE users SET last_step=?,failures=0,blocked_until=0 WHERE name=?",
                               (step, name))
            allowed = detail in ("", "OTP bypassed by administrator policy")
            self.audit(db, "otp.authentication", name, node,
                       "success" if allowed else "failed", detail)
        return allowed


def initialize(config):
    root = config.otp.data_dir
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if root.is_symlink() or root.stat().st_mode & 0o077:
        raise OTPError("OTP directory must be private (0700)")
    db_path = root / "otp.db"
    credential_paths = [root / "encryption.key", root / "admin.token"] + [
        root / (name + ".token") for name in config.otp.nodes]
    if db_path.exists() or any(path.exists() for path in credential_paths):
        raise OTPError("OTP already initialized or partially initialized; refusing to overwrite")
    for path in credential_paths:
        value = Fernet.generate_key().decode() if path.name == "encryption.key" else secrets.token_urlsafe(48)
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
            stream.write(value + "\n")
    with os.fdopen(os.open(db_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w"):
        pass
    with sqlite3.connect(db_path) as db:
        db.executescript("""
            CREATE TABLE settings (id INTEGER PRIMARY KEY CHECK(id=1), enforced INTEGER NOT NULL);
            INSERT INTO settings VALUES (1,0);
            CREATE TABLE users (
                name TEXT PRIMARY KEY, secret TEXT, pending TEXT, pending_until INTEGER DEFAULT 0,
                last_step INTEGER DEFAULT -1, failures INTEGER DEFAULT 0, blocked_until INTEGER DEFAULT 0
            );
            CREATE TABLE events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, at INTEGER NOT NULL, action TEXT NOT NULL,
                target TEXT, node TEXT, result TEXT, detail TEXT
            );
        """)


if __name__ == "__main__":
    import argparse
    from backend.config import load_config

    parser = argparse.ArgumentParser(description="Initialize OTP credentials and database without modifying OpenVPN")
    parser.add_argument("command", choices=["init"])
    parser.parse_args()
    initialize(load_config())
    print("OTP initialized. Enforcement is OFF. Credentials were saved to the configured data directory.")
