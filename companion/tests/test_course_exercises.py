import json
import uuid

import pytest
from companion.adapters.output import RecordingOutputPort
from companion.cognition.models import SituationAssessment
from companion.content.catalog import StrategyCatalog
from companion.core.api import CompanionCore
from companion.core.models import SessionState, TurnSignals
from companion.llm.fake import FakeLLM


@pytest.mark.parametrize("identifier", ["breathing_60s", "grounding", "bedtime"])
def test_exercise_filter_and_role_execution(config, store, identifier):
    assessment = SituationAssessment(
        expressed_need="solve", pathway_signals=("rumination",), support_constraints=("bedtime",)
    )
    state = SessionState(session_id="s", user_key="u")
    catalog = StrategyCatalog(config)
    assert identifier in {item["id"] for item in catalog.exercises(assessment, state)}
    assert not catalog.exercises(assessment.model_copy(update={"expressed_need": "listen"}), state)
    assert not catalog.exercises(
        assessment.model_copy(update={"support_constraints": ("unsafe_relationship",)}), state
    )
    if identifier == "bedtime":
        assert identifier not in {
            item["id"]
            for item in catalog.exercises(
                assessment.model_copy(update={"support_constraints": ()}), state
            )
        }
    state.exercises_refused.add(identifier)
    assert identifier not in {item["id"] for item in catalog.exercises(assessment, state)}

    fake = FakeLLM()
    fake.exercise_id = identifier  # Explicit targeted coverage, not natural selection.
    core = CompanionCore(config, store, fake)
    port = RecordingOutputPort(core.on_playback_event, auto_complete=False)
    core.bind_output("s", "u", port)

    def say(text):
        turn_id = core.on_input("s", uuid.uuid4().hex, text, TurnSignals())
        for event in core.respond("s", turn_id):
            core.dispatch(event)

    try:
        say("我想试一个练习")
        assert core.wait_idle()
        plan = store.active_support_plan("s")
        assert plan and plan.candidate_actions[0].action_id == identifier
        say("好")
        assert port.events[-1].text == config.exercises[identifier].protocol.invitation
        assert core.sessions["s"].state.mode == "normal"
        say("好")
        output = port.events[-1]
        assert output.type == "exercise_plan" and output.plan.script_id == identifier
        assert output.support.identifier == identifier and output.support.step == 1
        assert core.sessions["s"].state.mode == "exercise"
        say("刚才这个练习没帮助，停一下")
        assert core.sessions["s"].state.mode == "normal"
        assert core.sessions["s"].state.pending_offer is None
        assert identifier in core.sessions["s"].state.exercises_refused
        port.acknowledge(output, "completed")
        assert core.sessions["s"].state.mode == "normal"
        feedback = [
            json.loads(row["data"])
            for row in store.query(
                "SELECT data FROM interaction_events WHERE event_type='explicit_feedback'"
            )
        ]
        assert feedback[-1]["payload"]["support"]["identifier"] == identifier
        memory = next(m for m in store.memory_items("u") if m.kind == "support_experience")
        assert memory.support.identifier == identifier and memory.feedback_valence == "negative"
        assert memory.mention_policy == "only_when_raised"
        assert core.wait_idle()
    finally:
        core.close()


@pytest.mark.parametrize("identifier", ["breathing_60s", "grounding", "bedtime"])
def test_exercise_refusal_does_not_execute_or_reoffer(config, store, identifier):
    fake = FakeLLM()
    fake.exercise_id = identifier
    core = CompanionCore(config, store, fake)
    port = RecordingOutputPort(core.on_playback_event)
    core.bind_output("s", "u", port)
    try:
        for text in ("我想试一个练习", "好", "不愿意做这个练习", "还是听我说吧"):
            turn = core.on_input("s", uuid.uuid4().hex, text, TurnSignals())
            for event in core.respond("s", turn):
                core.dispatch(event)
            assert core.wait_idle()
        assert not any(event.type == "exercise_plan" for event in port.events)
        assert identifier in core.sessions["s"].state.exercises_refused
        assert core.sessions["s"].state.pending_offer is None
    finally:
        core.close()


def test_explicit_exercise_choice_cannot_be_replaced_by_another(config):
    catalog = StrategyCatalog(config)
    state = SessionState(session_id="s", user_key="u")
    assessment = SituationAssessment(
        expressed_need="solve", pathway_signals=("sleep",), support_constraints=("bedtime",)
    )
    selected = catalog.exercises(assessment, state, "我想做睡前暂停练习")
    assert [item["id"] for item in selected] == ["bedtime"]
    assert not catalog.exercises(
        assessment.model_copy(update={"support_constraints": ("bedtime", "body_focus_distress")}),
        state,
        "我想做睡前暂停练习",
    )
