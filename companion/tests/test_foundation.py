import sqlite3

import pytest
from companion.core.config import Config
from companion.core.models import SessionState, Snapshot, TurnSignals
from pydantic import ValidationError


def test_config_has_every_stage_and_rejects_unreviewed_demo(config):
    assert len(config.exercises) == 3
    with pytest.raises(ValueError, match="approved cards"):
        Config(mode="demo")


def test_snapshot_is_deeply_immutable():
    snapshot = Snapshot(session_id="s", user_key="u")
    with pytest.raises(ValidationError):
        snapshot.assessment.seeker_state.readiness = "high"
    assert isinstance(snapshot.allowed_cards, tuple)


def test_store_persists_and_uniquely_identifies_inputs(store):
    state = SessionState(session_id="s", user_key="u")
    store.create_session(state)
    turn_id = store.add_input(state, "input-1", "hello", "user", TurnSignals())
    assert store.existing_input("s", "input-1")["id"] == turn_id
    with pytest.raises(sqlite3.IntegrityError):
        store.add_input(state, "input-1", "hello", "user", TurnSignals())
    assert len(store.history("s")) == 1
    assert store.query("PRAGMA journal_mode")[0]["journal_mode"] == "wal"


def test_session_collections_are_not_shared():
    first = SessionState(session_id="a", user_key="a")
    second = SessionState(session_id="b", user_key="b")
    first.cards_refused.add("S16")
    assert not second.cards_refused
