"""Transactional, idempotent v1 -> v2 migration with a SQLite-consistent backup."""

import json
import sqlite3
import uuid
from pathlib import Path

from companion.cognition.base import EvidenceRef, utcnow
from companion.memory.models import MemoryItem

from .lease import WriterLease


def statements(db, path):
    # These packaged resources contain DDL only, no triggers/embedded semicolons.
    for statement in path.read_text(encoding="utf-8").split(";"):
        if statement.strip():
            db.execute(statement)


def import_legacy(db):
    for table in ("profile", "events"):
        for row in db.execute(f"SELECT * FROM {table}").fetchall():
            ids = json.loads(row["source_turn_ids"])
            valid_ids = [
                i
                for i in ids
                if db.execute(
                    "SELECT 1 FROM turns WHERE id=? AND user_key=? AND role='user'",
                    (i, row["user_key"]),
                ).fetchone()
            ]
            verified = bool(ids) and len(ids) == len(valid_ids)
            old_key = (
                f"{table}:{row['user_key']}:{row['field'] if table == 'profile' else row['id']}"
            )
            item = MemoryItem(
                memory_id=uuid.uuid5(uuid.NAMESPACE_URL, old_key).hex,
                user_key=row["user_key"],
                kind="fact_preference" if table == "profile" else "episodic_event",
                key=row["field"] if table == "profile" else f"legacy_event:{row['id']}",
                value=row["value"] if table == "profile" else row["summary"],
                epistemic_status="stated" if verified else "legacy_unverified",
                source_refs=tuple(
                    EvidenceRef(kind="user_turn", id=i, claim="v1 source") for i in (ids or [0])
                ),
                scope="persistent",
                mention_policy="only_when_raised",
                source_cursor=max(valid_ids, default=0),
            )
            db.execute(
                "INSERT INTO memory_items VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    item.memory_id,
                    item.user_key,
                    item.kind,
                    item.key,
                    item.scope,
                    None,
                    None,
                    item.status,
                    item.version,
                    None,
                    item.source_cursor,
                    item.model_dump_json(),
                    old_key,
                ),
            )
            for ref in item.source_refs:
                db.execute(
                    "INSERT OR IGNORE INTO memory_sources VALUES (?,?,?)",
                    (item.memory_id, ref.kind, str(ref.id)),
                )


def migrate(connection: sqlite3.Connection, path: Path) -> Path | None:
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version > 2 or version < 0:
        raise ValueError(f"Unsupported database version: {version}")
    if version == 2:
        return None
    lease = WriterLease(path)
    backup = None
    try:
        if version == 1:
            stamp = utcnow().strftime("%Y%m%dT%H%M%S%fZ")
            backup = path.with_name(f"{path.name}.v1-{stamp}.backup")
            with sqlite3.connect(backup) as destination:
                connection.backup(destination)
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            if version == 0:
                statements(connection, Path(__file__).with_name("schema.sql"))
            statements(connection, Path(__file__).with_name("migrations") / "002.sql")
            import_legacy(connection)
            connection.execute("PRAGMA user_version=2")
        return backup
    finally:
        lease.close()
