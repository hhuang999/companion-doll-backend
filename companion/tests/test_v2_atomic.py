import json
import sqlite3

import pytest
from companion.adapters.output import RecordingOutputPort
from companion.core.api import CompanionCore
from companion.core.models import TurnSignals
from companion.llm.fake import FakeLLM
from test_v2_cognition import input_turn


def test_v2_input_control_transaction_failure_stops_audio_and_keeps_database(
    config, store, monkeypatch
):
    core = CompanionCore(config, store, FakeLLM())
    port = RecordingOutputPort(core.on_playback_event)
    core.bind_output("s", "u", port)
    input_turn(core, "今天有点累")
    before = store.query("SELECT state FROM sessions")[0]["state"]
    original = store.save_state

    def fail(state):
        raise sqlite3.OperationalError("injected disk failure")

    try:
        monkeypatch.setattr(store, "save_state", fail)
        with pytest.raises(sqlite3.OperationalError):
            core.on_input("s", "fail", "今天别问论文", TurnSignals())
        assert store.query("SELECT state FROM sessions")[0]["state"] == before
        assert not store.query(
            "SELECT * FROM interaction_events WHERE event_type='boundary_requested'"
        )
        assert not store.memory_items("u")
        assert core.sessions["s"].persistence_failed
        with pytest.raises(RuntimeError, match="persistence"):
            input_turn(core, "下一轮")
    finally:
        monkeypatch.setattr(store, "save_state", original)
        core.close()


def test_v2_publication_rollback_keeps_memory_plan_and_state_consistent(config, store, monkeypatch):
    fake = FakeLLM()
    core = CompanionCore(config, store, fake)
    core.bind_output("s", "u", RecordingOutputPort(core.on_playback_event))
    input_turn(core, "今天考试失败了")
    original = store.finish_job

    def fail(job_id, status, **kwargs):
        if status == "completed" and kwargs.get("db") is not None:
            raise sqlite3.OperationalError("injected publication failure")
        return original(job_id, status, **kwargs)

    try:
        monkeypatch.setattr(store, "finish_job", fail)
        core.reasoner.submit("u", "s", "periodic")
        assert core.wait_idle()
        assert not store.query("SELECT * FROM support_plans")
        assert core.sessions["s"].state.support_plan_version == 0
        assert (
            json.loads(store.query("SELECT state FROM sessions")[0]["state"])[
                "support_plan_version"
            ]
            == 0
        )
        assert store.query("SELECT status FROM cognitive_jobs")[0]["status"] == "failed"
    finally:
        monkeypatch.setattr(store, "finish_job", original)
        core.close()


def test_v2_20_end_followup_recovery_is_idempotent(config, store):
    from companion.core.models import SessionState

    state = SessionState(session_id="abandoned", user_key="u")
    store.create_session(state)
    identifier = store.add_input(state, "1", "明天有考试", "user", TurnSignals())
    fake = FakeLLM(
        roles={
            "end": [
                lambda p: {
                    "summary_evidence": [
                        {
                            "kind": "user_turn",
                            "id": identifier,
                            "claim": "用户原话",
                            "quote": "明天有考试",
                        }
                    ],
                    "followups": [
                        {
                            "content": "考试进展",
                            "due_date": p["today"],
                            "evidence": [
                                {
                                    "kind": "user_turn",
                                    "id": identifier,
                                    "claim": "明确事件",
                                    "quote": "明天有考试",
                                }
                            ],
                        }
                    ],
                }
            ]
        }
    )
    core = CompanionCore(config, store, fake)
    try:
        assert core.wait_idle()
        assert store.query("SELECT status FROM end_tasks")[0]["status"] == "done"
        assert len(store.query("SELECT * FROM followups")) == 1
    finally:
        core.close()
    core = CompanionCore(config, store, FakeLLM())
    try:
        assert core.wait_idle()
        assert len(store.query("SELECT * FROM followups")) == 1
        assert len(store.query("SELECT * FROM cognitive_jobs")) == 1
    finally:
        core.close()
