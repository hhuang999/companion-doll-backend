import json
import sqlite3
from pathlib import Path

import pytest
from companion.core.models import SessionState, TurnSignals
from companion.store import Store
from companion.store.lease import WriterLease


def v1_database(path):
    db = sqlite3.connect(path)
    schema = Path(__file__).parents[1] / "companion/store/schema.sql"
    db.executescript(schema.read_text())
    state = SessionState(session_id="old", user_key="u")
    db.execute("INSERT INTO users VALUES ('u','2026-11-03T00:00:00+00:00',1)")
    db.execute(
        "INSERT INTO sessions(session_id,user_key,started_at,state) VALUES ('old','u',?,?)",
        (state.started_at.isoformat(), state.model_dump_json()),
    )
    db.execute(
        "INSERT INTO turns(id,session_id,user_key,input_id,role,text,created_at) VALUES (1,'old','u','1','user','我叫小林','2026-11-03T00:00:00+00:00')"
    )
    db.execute(
        "INSERT INTO profile VALUES ('u','nickname','小林',1,'[1]','2026-11-03T00:00:00+00:00')"
    )
    db.execute(
        "INSERT INTO profile VALUES ('u','notes','unverified',99,'[99]','2026-11-03T00:00:00+00:00')"
    )
    db.commit()
    db.close()


def test_v2_19_migration_preserves_sources_backup_and_is_idempotent(tmp_path):
    path = tmp_path / "old.db"
    v1_database(path)
    store = Store(path)
    assert store.query("PRAGMA user_version")[0]["user_version"] == 2
    assert store.query("SELECT onboarding_done FROM users")[0]["onboarding_done"] == 1
    rows = store.query("SELECT data FROM memory_items ORDER BY key")
    assert [json.loads(r["data"])["epistemic_status"] for r in rows] == [
        "stated",
        "legacy_unverified",
    ]
    backup = store.migration_backup
    assert backup.is_file()
    with sqlite3.connect(backup) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1
    store.close()
    store = Store(path)
    assert len(store.query("SELECT * FROM memory_items")) == 2
    assert store.migration_backup is None
    store.close()


def test_v2_19_migration_failure_rolls_back_and_active_writer_refused(tmp_path, monkeypatch):
    import companion.store.migrate as migration

    path = tmp_path / "failure.db"
    v1_database(path)
    lease = WriterLease(path)
    with pytest.raises(RuntimeError, match="active"):
        Store(path)
    lease.close()
    original = migration.import_legacy

    def interrupted(db):
        original(db)
        raise RuntimeError("injected migration interruption")

    monkeypatch.setattr(migration, "import_legacy", interrupted)
    with pytest.raises(RuntimeError, match="interruption"):
        Store(path)
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM profile").fetchone()[0] == 2
        assert not db.execute("SELECT 1 FROM sqlite_master WHERE name='memory_items'").fetchone()


def test_v2_19_future_schema_is_rejected(tmp_path):
    path = tmp_path / "future.db"
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA user_version=999")
    with pytest.raises(ValueError, match="Unsupported"):
        Store(path)


def test_v2_07_event_identity_and_nested_transaction_rollback(store):
    from companion.cognition.models import InteractionEvent

    state = SessionState(session_id="s", user_key="u")
    store.create_session(state)
    with pytest.raises(RuntimeError), store.transaction():
        store.add_input(state, "x", "temporary", "user", TurnSignals())
        raise RuntimeError("failure before state commit")
    assert not store.history("s")
    event = InteractionEvent(
        event_id="e",
        idempotency_key="e",
        user_key="wrong",
        session_id="s",
        event_type="session_ended",
        origin="deterministic_rule",
    )
    with pytest.raises(ValueError, match="identity"):
        store.record_interaction(event)
