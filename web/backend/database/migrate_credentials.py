"""Migrate existing user auth data into user_credentials.

Run once:
    python -m web.backend.database.migrate_credentials
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from fastapi import HTTPException
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from web.backend.database.database import Base
from web.backend.services.credential import bind_credential


DATABASE_PATHS = [
    Path("/root/subskin/data/subskin.db"),
    Path("/root/subskin/web/backend/data/subskin.db"),
]


def _create_session_factory(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _skip_existing_credential(error: HTTPException) -> bool:
    return error.status_code == 400


def _migrate_user_credentials(db: Session, user_row: dict[str, object]) -> None:
    user_id = cast(int, user_row["id"])
    phone = cast(str | None, user_row.get("phone"))
    email = cast(str | None, user_row.get("email"))
    hashed_password = cast(str | None, user_row.get("hashed_password"))
    wechat_id = cast(str | None, user_row.get("wechat_id"))
    alipay_id = cast(str | None, user_row.get("alipay_id"))

    if phone:
        try:
            bind_credential(db, user_id, "phone", phone, verified=True)
        except HTTPException as exc:
            if not _skip_existing_credential(exc):
                raise
            db.rollback()

    if email:
        try:
            bind_credential(db, user_id, "email", email, verified=True)
        except HTTPException as exc:
            if not _skip_existing_credential(exc):
                raise
            db.rollback()

    if hashed_password:
        try:
            bind_credential(
                db,
                user_id,
                "password",
                "password",
                verified=True,
                credential_data=json.dumps(
                    {"hashed_password": hashed_password}, ensure_ascii=False
                ),
            )
        except HTTPException as exc:
            if not _skip_existing_credential(exc):
                raise
            db.rollback()

    if wechat_id:
        try:
            bind_credential(db, user_id, "wechat", wechat_id, verified=True)
        except HTTPException as exc:
            if not _skip_existing_credential(exc):
                raise
            db.rollback()

    if alipay_id:
        try:
            bind_credential(db, user_id, "alipay", alipay_id, verified=True)
        except HTTPException as exc:
            if not _skip_existing_credential(exc):
                raise
            db.rollback()


def _load_legacy_users(db: Session) -> list[dict[str, object]]:
    available_columns = {
        column["name"] for column in inspect(db.get_bind()).get_columns("users")
    }
    requested_columns = [
        "id",
        "phone",
        "email",
        "hashed_password",
        "wechat_id",
        "alipay_id",
    ]
    select_parts = []
    for column in requested_columns:
        if column in available_columns:
            select_parts.append(column)
        else:
            select_parts.append(f"NULL AS {column}")

    result = db.execute(text(f"SELECT {', '.join(select_parts)} FROM users"))
    return [dict(row._mapping) for row in result]


def migrate_database(db_path: Path) -> None:
    session_factory = _create_session_factory(db_path)
    db = session_factory()
    try:
        users = _load_legacy_users(db)
        for user_row in users:
            _migrate_user_credentials(db, user_row)
    finally:
        db.close()


def main() -> None:
    for db_path in DATABASE_PATHS:
        migrate_database(db_path)
        print(f"Migrated credentials for {db_path}")


if __name__ == "__main__":
    main()
