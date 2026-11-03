import threading
import time

from companion.adapters.output import RecordingOutputPort
from companion.core.api import CompanionCore
from companion.core.models import (
    RiskResult,
    SessionState,
    Snapshot,
    Stage,
    TurnContext,
    TurnSignals,
)
from companion.core.state_machine import StateMachine
from companion.core.talker import Talker
from companion.llm.fake import FakeLLM


def test_restart_finalizes_abandoned_session(config, store):
    state = SessionState(session_id="abandoned", user_key="u")
    store.create_session(state)
    store.add_input(state, "1", "今天考试难受", "user", TurnSignals())
    core = CompanionCore(config, store, FakeLLM())
    try:
        assert core.wait_idle()
        row = store.query("SELECT lifecycle,summary FROM sessions")[0]
        assert row["lifecycle"] == "closed" and row["summary"]
        assert store.query("SELECT status FROM end_tasks")[0]["status"] == "done"
    finally:
        core.close()


def test_high_callback_is_idempotent_and_fast(config, store):
    core = CompanionCore(config, store, FakeLLM())
    output = RecordingOutputPort(core.on_playback_event)
    core.bind_output("s", "u", output)
    try:
        identifier = core.on_input("s", "1", "hello", TurnSignals())
        assert core.wait_idle()
        risk = RiskResult(level="high", source="model")
        started = time.monotonic()
        core._risk_result("s", identifier, risk, 601)
        assert (time.monotonic() - started) * 1000 < 100
        with store.transaction() as db:
            db.execute("UPDATE risk_events SET handled=1")
        core._risk_result("s", identifier, risk, 601)
        assert len(output.events) == 1
        assert store.query("SELECT handled FROM risk_events")[0]["handled"] == 1
    finally:
        core.close()


def test_closing_does_not_repeat_after_two_replies(config):
    state = SessionState(session_id="s", user_key="u", stage=Stage.closing, closing_turns=2)
    result = StateMachine(config).apply_rules(
        state, "嗯", TurnSignals(), Snapshot(session_id="s", user_key="u")
    )
    assert result.directive == "quiet"
    assert state.stage == Stage.quiet


def test_long_malformed_tag_is_never_spoken(config):
    text = "<<" + "metadata" * 100 + ">>\n我在这里陪你。"
    context = TurnContext(
        session_id="s",
        turn_id=1,
        generation=1,
        text="hello",
        kind="user",
        stage=Stage.explore,
        mode="normal",
        snapshot=Snapshot(session_id="s", user_key="u"),
        signals=TurnSignals(),
        t0=time.monotonic(),
    )
    outputs = list(
        Talker(config, FakeLLM(streams=[text])).run(context, [], threading.Event(), {}, [])
    )
    assert [text for text, _ in outputs] == ["我在这里陪你。"]
