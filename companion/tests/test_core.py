import threading
import time

import pytest
from companion.adapters.output import RecordingOutputPort
from companion.core.api import CompanionCore
from companion.core.models import RiskResult, Stage, TurnSignals
from companion.llm.fake import FakeLLM


@pytest.fixture
def core(config, store):
    value = CompanionCore(config, store, FakeLLM())
    yield value
    value.close()


def bind(core, session="s", user="u", auto=True):
    port = RecordingOutputPort(core.on_playback_event, auto_complete=auto)
    core.bind_output(session, user, port)
    return port


def turn(core, text, session="s", kind="user", signals=None):
    import uuid

    identifier = core.on_input(session, uuid.uuid4().hex, text, signals or TurnSignals(), kind)
    for event in core.respond(session, identifier):
        core.dispatch(event)
    return identifier


def test_first_opening_only_commits_after_playback(core):
    port = bind(core, auto=False)
    turn(core, "", kind="wake")
    assert not core.store.onboarding_done("u")
    port.acknowledge(port.events[0], "completed")
    assert core.store.onboarding_done("u")
    assert core.sessions["s"].state.stage == Stage.explore


def test_direct_help_full_flow_and_action_count(core):
    bind(core)
    turn(core, "", kind="wake")
    turn(core, "这件事情反复困扰我，怎么办")
    assert core.wait_idle()
    turn(core, "好，你说")
    assert core.sessions["s"].state.stage == Stage.action
    assert core.sessions["s"].state.cards_used == {"S16": 1}
    turn(core, "那天老师发下试卷，我很难过")
    assert core.sessions["s"].state.cards_used == {"S16": 1}


def test_high_risk_bypasses_models_and_is_sticky(core):
    port = bind(core)
    identifier = turn(core, "我想自杀")
    assert not core.llm.calls
    assert core.sessions["s"].state.mode == "crisis"
    assert len(port.events) == 1
    assert port.events[0].type == "crisis_plan"
    turn(core, "我现在好些了")
    assert not core.llm.calls
    assert core.sessions["s"].state.mode == "crisis"
    assert (
        core.store.query("SELECT level FROM risk_events WHERE turn_id=?", (identifier,))[0]["level"]
        == "high"
    )


def test_late_high_risk_takes_over_without_next_turn(config, store):
    config.settings.timing.gate_timeout_ms = 5
    llm = FakeLLM(risks=[RiskResult(level="high", category="other")])
    llm.risk_release = threading.Event()
    core = CompanionCore(config, store, llm)
    port = bind(core)
    try:
        turn(core, "一句未命中词表的话")
        assert any(e.type == "text" for e in port.events)
        llm.risk_release.set()
        assert core.wait_idle(5)
        assert port.events[-1].type == "crisis_plan"
        assert core.sessions["s"].state.mode == "crisis"
    finally:
        llm.risk_release.set()
        core.close()


def test_exercise_checks_high_risk_and_ignores_old_completion(core):
    port = bind(core, auto=False)
    turn(core, "我好难受", signals=TurnSignals(events=("Cry",)))
    turn(core, "好")
    exercise = port.events[-1]
    assert exercise.type == "exercise_plan"
    assert core.sessions["s"].state.mode == "exercise"
    turn(core, "我想自杀")
    port.acknowledge(exercise, "completed")
    assert core.sessions["s"].state.mode == "crisis"


def test_duplicate_input_does_not_cancel_or_duplicate(core):
    bind(core)
    one = core.on_input("s", "same", "hello", TurnSignals())
    generation = core.sessions["s"].state.generation
    two = core.on_input("s", "same", "hello", TurnSignals())
    assert one == two
    assert core.sessions["s"].state.generation == generation
    with pytest.raises(ValueError, match="reused"):
        core.on_input("s", "same", "different", TurnSignals())


def test_cancellation_rejects_old_output(core):
    port = bind(core)
    identifier = core.on_input("s", "one", "hello", TurnSignals())
    iterator = core.respond("s", identifier)
    old = next(iterator)
    core.on_input("s", "two", "another", TurnSignals())
    assert not core.dispatch(old)
    iterator.close()
    assert not port.events


def test_old_reasoner_is_rejected_and_end_task_survives(config, store):
    llm = FakeLLM()
    llm.reasoner_release = threading.Event()
    core = CompanionCore(config, store, llm)
    bind(core)
    try:
        turn(core, "怎么办")
        deadline = time.monotonic() + 3
        while "analysis" not in llm.calls and time.monotonic() < deadline:
            time.sleep(0.005)
        turn(core, "不想说了")
        core.on_session_end("s", "test")
        bind(core, "new", "u")
        llm.reasoner_release.set()
        assert core.wait_idle(5)
        assert (
            core.store.query("SELECT status FROM end_tasks WHERE session_id='s'")[0]["status"]
            == "done"
        )
        assert core.sessions["new"].state.stage == Stage.opening
        assert (
            core.store.query(
                "SELECT status FROM cognitive_jobs WHERE session_id='s' ORDER BY queued_at"
            )[0]["status"]
            == "cancelled"
        )
    finally:
        llm.reasoner_release.set()
        core.close()


def test_users_are_isolated_and_purge_is_complete(core):
    bind(core)
    bind(core, "s2", "u2")
    turn(core, "我想自杀")
    turn(core, "hello", session="s2")
    assert core.sessions["s2"].state.mode == "normal"
    core.purge_user("u")
    assert not core.store.query("SELECT * FROM users WHERE user_key='u'")
    assert core.store.query("SELECT * FROM users WHERE user_key='u2'")


def test_model_failure_uses_fallback_but_cancel_does_not(core):
    port = bind(core)
    core.llm.streams.append(RuntimeError("test failure"))
    identifier = turn(core, "hello")
    assert port.events[-1].text == core.config.stages["explore"]["fallback"]
    assert (
        "llm_error"
        in core.store.query("SELECT violations FROM turns WHERE id=?", (identifier,))[0][
            "violations"
        ]
    )
