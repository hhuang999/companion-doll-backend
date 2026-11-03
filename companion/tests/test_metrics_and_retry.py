import json
import sys

from companion.core.models import SessionState, TurnSignals
from companion.tools.retry_end import main


def test_async_metrics_merge_without_dropping_earlier_fields(store):
    state = SessionState(session_id="s", user_key="u")
    store.create_session(state)
    identifier = store.add_input(state, "1", "hello", "user", TurnSignals())
    store.update_turn(identifier, latency={"gate_release_ms": 600})
    store.update_turn(identifier, latency={"risk_l2_ms": 800, "risk_status": "ok"})
    metrics = json.loads(store.query("SELECT latency FROM turns")[0]["latency"])
    assert metrics == {"gate_release_ms": 600, "risk_l2_ms": 800, "risk_status": "ok"}


def test_failed_end_can_be_explicitly_retried(store, monkeypatch):
    state = SessionState(session_id="failed", user_key="u")
    store.create_session(state)
    state.latest_turn_id = store.add_input(state, "1", "今天考试失落", "user", TurnSignals())
    state.lifecycle = "ending"
    store.end_session(state, "test")
    store.fail_end("failed", "test failure")
    monkeypatch.setattr(sys, "argv", ["retry-end", "failed", "--db", str(store.path), "--fake"])
    main()
    assert store.query("SELECT status FROM end_tasks")[0]["status"] == "done"
    assert store.query("SELECT summary FROM sessions")[0]["summary"]
