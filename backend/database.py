from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from backend.config import OpenVPNUIConfig


def sqlite_path_from_url(database_url: str) -> Path:
    if database_url.startswith("sqlite:////"):
        return Path("/" + database_url.removeprefix("sqlite:////"))
    if database_url.startswith("sqlite:///"):
        return Path(database_url.removeprefix("sqlite:///"))
    raise ValueError("Only sqlite:/// database URLs are supported")


@contextmanager
def connect(config: OpenVPNUIConfig) -> Iterator[sqlite3.Connection]:
    path = sqlite_path_from_url(config.app.database_url)
    if path.parent != Path("."):
        path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    try:
        ensure_schema(db)
        yield db
        db.commit()
    finally:
        db.close()


def ensure_schema(db: sqlite3.Connection) -> None:
    db.execute(
        """
        create table if not exists audit_events (
            id integer primary key autoincrement,
            timestamp text not null default current_timestamp,
            actor text not null,
            action text not null,
            target text,
            reason text,
            result text not null,
            error text
        )
        """
    )
    db.execute(
        """
        create table if not exists user_overrides (
            common_name text primary key,
            disabled integer not null default 0,
            updated_at text not null default current_timestamp
        )
        """
    )


def add_audit_event(
    config: OpenVPNUIConfig,
    action: str,
    target: str = "",
    reason: str = "",
    result: str = "success",
    error: str = "",
    actor: str = "local-admin",
) -> None:
    with connect(config) as db:
        db.execute(
            """
            insert into audit_events (actor, action, target, reason, result, error)
            values (?, ?, ?, ?, ?, ?)
            """,
            (actor, action, target, reason, result, error),
        )


def list_audit_events(config: OpenVPNUIConfig, limit: int = 200) -> list[dict[str, object]]:
    with connect(config) as db:
        rows = db.execute(
            """
            select id, timestamp, actor, action, target, reason, result, error
            from audit_events
            order by id desc
            limit ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def set_user_disabled(config: OpenVPNUIConfig, common_name: str, disabled: bool) -> None:
    with connect(config) as db:
        db.execute(
            """
            insert into user_overrides (common_name, disabled, updated_at)
            values (?, ?, current_timestamp)
            on conflict(common_name) do update set
                disabled = excluded.disabled,
                updated_at = current_timestamp
            """,
            (common_name, 1 if disabled else 0),
        )


def get_disabled_users(config: OpenVPNUIConfig) -> set[str]:
    with connect(config) as db:
        rows = db.execute(
            "select common_name from user_overrides where disabled = 1"
        ).fetchall()
    return {str(row["common_name"]) for row in rows}
