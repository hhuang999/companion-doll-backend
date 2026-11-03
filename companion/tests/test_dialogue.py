import threading
import time

import pytest
from companion.core.models import (
    Assessment,
    SeekerState,
    SessionState,
    Snapshot,
    Stage,
    StageProposal,
    TurnContext,
    TurnSignals,
)
from companion.core.state_machine import StateMachine
from companion.core.talker import Talker
from companion.llm.fake import FakeLLM


def test_consent_waits_for_card_and_survives_clarification(config):
    machine = StateMachine(config)
    state = SessionState(
        session_id="s", user_key="u", stage=Stage.explore, user_turns=1, latest_turn_id=1
    )
    snapshot = Snapshot(session_id="s", user_key="u")
    assert machine.apply_rules(state, "怎么办", TurnSignals(), snapshot).directive == "action_offer"
    state.pending_offer.active = True
    state.user_turns = 2
    machine.apply_rules(state, "好，你说", TurnSignals(), snapshot, now=100)
    assert state.pending_offer.status == "accepted_waiting_card"
    state.user_turns = 3
    snapshot = snapshot.model_copy(
        update={
            "allowed_cards": ("S16",),
            "preferred_card": "S16",
            "assessment": Assessment(seeker_state=SeekerState(readiness="medium")),
        }
    )
    machine.apply_rules(state, "数学最让我担心", TurnSignals(), snapshot, now=101)
    assert state.stage == Stage.action
    assert state.card_in_use == "S16"


@pytest.mark.parametrize("text", ["好难受", "不可以", "我不愿意"])
def test_consent_is_not_substring_match(config, text):
    assert not StateMachine(config).matches("agree", text)


def test_quiet_has_priority_over_request(config):
    state = SessionState(session_id="s", user_key="u", stage=Stage.explore)
    StateMachine(config).apply_rules(
        state, "怎么办，不想说了", TurnSignals(), Snapshot(session_id="s", user_key="u")
    )
    assert state.stage == Stage.quiet
    assert state.pending_offer is None


def test_talker_streaming_strips_tags_and_blocks_advice(config):
    llm = FakeLLM(streams=["<<state=action;card=S16;emo=🤔;offer=->>\n你应该努力。听起来你很累。"])
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
    violations = []
    sentences = list(Talker(config, llm).run(context, [], threading.Event(), {}, violations))
    assert [s[0] for s in sentences] == ["听起来你很累。"]
    assert set(violations) >= {"tag_state_mismatch", "card_not_allowed", "rail_lecture"}


def test_no_question_in_quiet_fallback(config):
    assert "？" not in config.stages["quiet"]["fallback"]


def test_evidenced_topic_change_revokes_pending_offer(config):
    machine = StateMachine(config)
    state = SessionState(session_id="s", user_key="u", stage=Stage.permission)
    machine.offer(state, "action")
    snapshot = Snapshot(
        session_id="s",
        user_key="u",
        version=1,
        topic_changed=True,
        stage_proposal=StageProposal(to=Stage.explore, reason="new topic", source_turn_ids=(1,)),
    )
    result = machine.apply_rules(state, "其实还有别的事情", TurnSignals(), snapshot)
    assert state.stage == Stage.explore and state.pending_offer is None
    assert state.topic_revision == 1 and "Q4" in result.fired_rules


def test_card_readiness_checked_again_before_action(config):
    config.cards["S16"].constraints["excluded_readiness"] = ["low"]
    snapshot = Snapshot(session_id="s", user_key="u", allowed_cards=("S16",))
    assert StateMachine(config).eligible(SessionState(session_id="s", user_key="u"), snapshot) == []


def test_plain_speech_yields_first_sentence_before_stream_finishes(config):
    class DelayedRemainder:
        def stream_chat(self, *args, **kwargs):
            yield "听起来这件事让你很累。"
            raise AssertionError("Must yield speech before reading the next chunk")

    context = TurnContext(
        session_id="s",
        turn_id=1,
        generation=1,
        text="很累",
        kind="user",
        stage=Stage.explore,
        mode="normal",
        snapshot=Snapshot(session_id="s", user_key="u"),
        signals=TurnSignals(),
        t0=time.monotonic(),
    )
    violations = []
    stream = Talker(config, DelayedRemainder()).run(context, [], threading.Event(), {}, violations)
    assert next(stream)[0] == "听起来这件事让你很累。"
    assert not violations
    stream.close()


def test_cross_turn_question_budget(config):
    context = TurnContext(
        session_id="s",
        turn_id=2,
        generation=2,
        text="是啊，很累",
        kind="user",
        stage=Stage.explore,
        mode="normal",
        snapshot=Snapshot(session_id="s", user_key="u"),
        signals=TurnSignals(),
        t0=time.monotonic(),
    )
    history = [{"role": "assistant", "text": "最近最累的是什么？"}]
    violations = []
    result = list(
        Talker(config, FakeLLM(streams=["听起来很累。能再讲讲吗？"])).run(
            context, history, threading.Event(), {}, violations
        )
    )
    assert [sentence for sentence, _ in result] == ["听起来很累。"]
    assert "rail_questions" in violations


def test_reported_choice_does_not_revoke_action(config):
    machine = StateMachine(config)
    state = SessionState(
        session_id="s", user_key="u", stage=Stage.action, card_in_use="safe_support"
    )
    machine.apply_rules(
        state,
        "姑姑会先问我愿不愿意说，我觉得她相对安全。",
        TurnSignals(),
        Snapshot(session_id="s", user_key="u"),
    )
    assert state.stage == Stage.action
    assert state.card_in_use == "safe_support"
    machine.apply_rules(
        state, "我不愿意继续", TurnSignals(), Snapshot(session_id="s", user_key="u")
    )
    assert state.stage != Stage.action


@pytest.mark.parametrize("text", ["我不想要办法，只是想说说。", "不要给建议", "只想说说"])
def test_listening_request_does_not_open_an_offer(config, text):
    state = SessionState(session_id="s", user_key="u", stage=Stage.explore)
    result = StateMachine(config).apply_rules(
        state, text, TurnSignals(), Snapshot(session_id="s", user_key="u")
    )
    assert state.pending_offer is None
    assert result.directive != "action_offer"


def test_closing_quote_is_not_a_spoken_segment(config):
    class Chunks:
        def stream_chat(self, *args, **kwargs):
            yield "可以这样说：我有点委屈。"
            yield "”"

    context = TurnContext(
        session_id="s",
        turn_id=1,
        generation=1,
        text="我有点委屈",
        kind="user",
        stage=Stage.action,
        mode="normal",
        snapshot=Snapshot(session_id="s", user_key="u"),
        signals=TurnSignals(),
        t0=time.monotonic(),
    )
    result = list(Talker(config, Chunks()).run(context, [], threading.Event(), {}, []))
    assert [text for text, _ in result] == ["可以这样说：我有点委屈。"]


def test_replay_advice_and_unfounded_effort_are_blocked(config):
    from companion.core.output_rail import OutputRail

    rail = OutputRail(config)
    assert "rail_advice" in rail.check("从一个让你心跳快的小问题开始试试？", Stage.explore)
    assert not rail.check("先从这个小问题试试。", Stage.action)
    assert "rail_cliche" in rail.check("你已经很努力在面对这些了。", Stage.explore)
