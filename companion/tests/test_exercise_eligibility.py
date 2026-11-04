import threading
import uuid

import pytest
from companion.adapters.output import RecordingOutputPort
from companion.core.api import CompanionCore
from companion.core.models import TurnSignals
from companion.llm.fake import FakeLLM


@pytest.mark.parametrize("phase", ["generic_offer", "specific_offer", "resume"])
@pytest.mark.parametrize("refresh", ["excluded", "eligible", "failed"])
def test_changed_conditions_require_fresh_exercise_review(config, store, phase, refresh):
    config.cards = {}
    # Keep the periodic trigger out of the test: the eligibility change must trigger review.
    config.settings.dialogue.reasoner_every_n_turns = 100
    entered, release = threading.Event(), threading.Event()
    analyses = 0

    def analysis(payload):
        nonlocal analyses
        analyses += 1
        if analyses > 1:
            entered.set()
            assert release.wait(5), "test did not release assessment"
            if refresh == "failed":
                raise TimeoutError("injected assessment timeout")
        latest = next(row for row in reversed(payload["history"]) if row["role"] == "user")
        return {
            "facts": [
                {
                    "statement": latest["text"],
                    "evidence": [
                        {"kind": "user_turn", "id": latest["id"], "claim": "当前合成输入"}
                    ],
                }
            ],
            "expressed_need": "solve",
            "pressure_types": ["academic"],
            "pathway_signals": ["rumination"],
            "readiness": "medium",
            "support_constraints": ["body_focus_distress"]
            if analyses > 1 and refresh == "excluded"
            else [],
        }

    fake = FakeLLM(roles={"analysis": [analysis] * 10})
    fake.exercise_id = "breathing_60s"
    core = CompanionCore(config, store, fake)
    port = RecordingOutputPort(core.on_playback_event, auto_complete=False)
    core.bind_output("s", "u", port)

    def say(text, signals=None):
        turn = core.on_input("s", uuid.uuid4().hex, text, signals or TurnSignals())
        events = list(core.respond("s", turn))
        for event in events:
            core.dispatch(event)
        return events

    try:
        say("我想试一个练习")
        assert core.wait_idle()
        if phase != "generic_offer":
            assert say("好")[-1].purpose == "exercise_offer"
        if phase == "resume":
            assert say("好")[-1].type == "exercise_plan"
            core.on_interrupt("s", core.sessions["s"].state.generation, "test interruption")
        start = len(port.events)
        say("我一关注呼吸就难受" if refresh == "excluded" else "我刚换了个地方")
        assert entered.wait(3), "new circumstances did not trigger reassessment"
        say("好")
        say("好")
        assert not any(
            event.type == "exercise_plan" or event.purpose in ("exercise_offer", "resume_offer")
            for event in port.events[start:]
        )
        release.set()
        assert core.wait_idle()
        if refresh == "eligible":
            invitation = say("好")[-1]
            assert invitation.purpose in ("exercise_offer", "resume_offer")
            assert core.sessions["s"].state.mode == "normal"
            assert say("好")[-1].type == "exercise_plan"
        else:
            say("好")
            assert not any(
                event.type == "exercise_plan" or event.purpose in ("exercise_offer", "resume_offer")
                for event in port.events[start:]
            )
            assert core.sessions["s"].state.mode == "normal"
            if refresh == "failed":
                assert store.query("SELECT 1 FROM cognitive_jobs WHERE status='timed_out'")
            else:
                assert not store.active_support_plan("s").candidate_actions
                if phase == "resume":
                    assert core.sessions["s"].state.resume_script_id is None
    finally:
        release.set()
        core.close()


@pytest.mark.parametrize(
    "signals,allowed",
    [
        (TurnSignals(emotion="NEUTRAL", events=("Speech",)), True),
        (TurnSignals(emotion="SAD", events=("Cry",)), False),
    ],
)
def test_consent_with_new_nonverbal_signals_requires_reassessment(config, store, signals, allowed):
    fake = FakeLLM()
    fake.exercise_id = "breathing_60s"
    core = CompanionCore(config, store, fake)
    port = RecordingOutputPort(core.on_playback_event, auto_complete=False)
    core.bind_output("s", "u", port)
    try:
        for text in ("我想试一个练习", "好"):
            turn = core.on_input("s", uuid.uuid4().hex, text, TurnSignals())
            for output in core.respond("s", turn):
                core.dispatch(output)
            assert core.wait_idle()
        turn = core.on_input("s", uuid.uuid4().hex, "好", signals)
        outputs = list(core.respond("s", turn))
        assert any(event.type == "exercise_plan" for event in outputs) is allowed
        assert (core.sessions["s"].state.mode == "exercise") is allowed
    finally:
        core.close()
