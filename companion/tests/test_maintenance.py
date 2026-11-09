import sqlite3
import sys

import pytest
from companion.adapters.cli import build_core
from companion.core.api import CompanionCore
from companion.core.models import SessionState
from companion.llm.fake import FakeLLM
from companion.store import Store
from companion.store.lease import WriterLease
from companion.tools import purge, retry_end


def test_offline_purge_refuses_a_database_owned_by_a_running_core(config, store, monkeypatch):
    core = build_core(config, store.path, fake=True)
    state = SessionState(session_id="closed", user_key="u")
    store.create_session(state)
    store.end_session(state, "test")
    store.fail_end(state.session_id, "test")
    monkeypatch.setattr(sys, "argv", ["purge", "u", "--db", str(store.path)])
    try:
        with pytest.raises(RuntimeError, match="active Core"):
            purge.main()
        assert store.query("SELECT user_key FROM users") == [{"user_key": "u"}]
    finally:
        core.close()
        core.store.close()
    purge.main()
    assert not store.query("SELECT * FROM users")


def test_retry_refuses_a_running_core_before_changing_the_failed_task(config, store, monkeypatch):
    state = SessionState(session_id="failed", user_key="u")
    store.create_session(state)
    store.end_session(state, "test")
    store.fail_end(state.session_id, "original failure")
    core = build_core(config, store.path, fake=True)
    monkeypatch.setattr(sys, "argv", ["retry-end", "failed", "--db", str(store.path), "--fake"])
    try:
        with pytest.raises(RuntimeError, match="active Core"):
            retry_end.main()
        assert store.query("SELECT status FROM end_tasks") == [{"status": "failed"}]
    finally:
        core.close()
        core.store.close()


def test_retry_configuration_failure_preserves_the_failed_task(store, monkeypatch):
    state = SessionState(session_id="failed", user_key="u")
    store.create_session(state)
    store.end_session(state, "test")
    store.fail_end(state.session_id, "original failure")
    monkeypatch.setattr(
        sys,
        "argv",
        ["retry-end", "failed", "--db", str(store.path), "--config-dir", "missing-config"],
    )
    with pytest.raises(FileNotFoundError):
        retry_end.main()
    assert store.query("SELECT status FROM end_tasks") == [{"status": "failed"}]


def test_failed_startup_releases_the_writer_lease(config, store, monkeypatch):
    def fail():
        raise sqlite3.OperationalError("recovery failed")

    monkeypatch.setattr(store, "recover", fail)
    with pytest.raises(sqlite3.OperationalError, match="recovery failed"):
        CompanionCore(config, store, FakeLLM())
    lease = WriterLease(store.path)
    lease.close()


def test_failed_client_initialization_closes_the_database(config, tmp_path, monkeypatch):
    from companion.adapters import cli

    store = Store(tmp_path / "startup.db")
    connection = store.connection()
    monkeypatch.setattr(cli, "Store", lambda *_: store)
    monkeypatch.delenv(config.settings.llm.api_key_env, raising=False)
    with pytest.raises(ValueError, match="Missing environment variable"):
        build_core(config, store.path)
    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        connection.execute("SELECT 1")
