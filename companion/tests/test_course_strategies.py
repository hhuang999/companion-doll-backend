import json
import uuid

import pytest
from companion.adapters.output import RecordingOutputPort
from companion.cognition.models import SituationAssessment
from companion.content.catalog import StrategyCatalog
from companion.core.api import CompanionCore
from companion.core.models import SessionState, Stage, TurnSignals
from companion.llm.fake import FakeLLM

CASES = [
    ("S16", "academic", "rumination", (), "我总想考试那道题卡住的地方，怎么办"),
    ("kind_self_talk", "self", "self_criticism", (), "总觉得一次没做好就是整个人不行，怎么办"),
    (
        "safe_communication",
        "relationship",
        None,
        ("safe_contact",),
        "我想跟不会伤害我的同桌解释误会，怎么办",
    ),
    (
        "safe_support",
        "relationship",
        "loneliness",
        (),
        "我觉得孤独又怕被评价，想找安全的人聊聊，怎么办",
    ),
    ("values_exploration", "future", None, (), "我对未来没有方向，想了解自己好奇的事，怎么办"),
    ("worry_parking", "academic", "sleep", ("bedtime",), "准备睡了还在担心明天的考试，怎么办"),
]


@pytest.mark.parametrize("identifier,pressure,pathway,contexts,text", CASES)
def test_each_course_strategy_filters_refusal_and_exclusions(
    config, identifier, pressure, pathway, contexts, text
):
    assessment = SituationAssessment(
        expressed_need="solve",
        pressure_types=(pressure,),
        pathway_signals=(pathway,) if pathway else (),
        readiness="medium",
        support_constraints=contexts,
    )
    state = SessionState(session_id="s", user_key="u")
    catalog = StrategyCatalog(config)

    def decision(value=assessment):
        return next(
            d for d in catalog.select(value, state, text).decisions if d.strategy_id == identifier
        )

    assert decision().eligible
    assert not decision(assessment.model_copy(update={"expressed_need": "listen"})).eligible
    assert not decision(assessment.model_copy(update={"emotion_intensity": "high"})).eligible
    card = config.cards[identifier]
    if card.protocol.required_contexts:
        assert (
            "missing_required_context"
            in decision(assessment.model_copy(update={"support_constraints": ()})).reasons
        )
    if card.protocol.excluded_contexts:
        assert (
            "context_excluded"
            in decision(
                assessment.model_copy(
                    update={"support_constraints": (*contexts, card.protocol.excluded_contexts[0])}
                )
            ).reasons
        )
    state.cards_refused.add(identifier)
    assert "refused_this_session" in decision().reasons


@pytest.mark.parametrize("identifier,pressure,pathway,contexts,text", CASES)
def test_each_strategy_runs_roles_permission_step_feedback_and_exit(
    config, store, identifier, pressure, pathway, contexts, text
):
    # Intentional forced-candidate coverage is distinct from natural-selection evaluation.
    config.cards = {identifier: config.cards[identifier]}

    def analysis(payload):
        latest = next(row for row in reversed(payload["history"]) if row["role"] == "user")
        return {
            "facts": [
                {
                    "statement": latest["text"],
                    "evidence": [
                        {"kind": "user_turn", "id": latest["id"], "claim": "合成情境原话"}
                    ],
                }
            ],
            "expressed_need": "solve",
            "pressure_types": [pressure],
            "pathway_signals": [pathway] if pathway else [],
            "readiness": "medium",
            "support_constraints": list(contexts),
        }

    fake = FakeLLM(roles={"analysis": [analysis]})
    core = CompanionCore(config, store, fake)
    port = RecordingOutputPort(core.on_playback_event)
    core.bind_output("s", "u", port)

    def say(message):
        turn = core.on_input("s", uuid.uuid4().hex, message, TurnSignals())
        events = list(core.respond("s", turn))
        for event in events:
            core.dispatch(event)
        return turn, events

    try:
        say(text)
        assert core.sessions["s"].state.stage == Stage.permission
        assert core.sessions["s"].state.card_in_use is None
        assert core.wait_idle()
        plan = store.active_support_plan("s")
        assert plan and plan.candidate_actions[0].action_id == identifier
        _turn, events = say("好，你说")
        assert core.sessions["s"].state.card_in_use == identifier
        assert events and events[0].text == fake.content["strategy_replies"][identifier][0]
        assert store.query("SELECT * FROM card_usage WHERE card_id=?", (identifier,))
        say("刚才这个办法没帮助，停一下")
        state = core.sessions["s"].state
        assert state.card_in_use is None and identifier in state.cards_refused
        feedback = [
            json.loads(r["data"])
            for r in store.query(
                "SELECT data FROM interaction_events WHERE event_type='explicit_feedback'"
            )
        ]
        assert feedback[-1]["payload"]["valence"] == "negative"
        assert feedback[-1]["payload"]["attribution"] == "explicit"
        assert any(m.kind == "support_experience" for m in store.memory_items("u"))
        assert core.wait_idle()
        assert state.card_in_use is None
    finally:
        core.close()
