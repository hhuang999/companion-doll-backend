import json
from datetime import datetime, timedelta, timezone

from companion.cognition.base import EvidenceRef
from companion.cognition.policy import effective_boundaries, prompt_projection
from companion.core.models import SessionState, TurnSignals
from companion.memory.models import MemoryCandidate
from companion.memory.service import MemoryService


def state_and_turn(store, text, session="s", user="u"):
    state = SessionState(session_id=session, user_key=user)
    store.create_session(state)
    state.latest_turn_id = store.add_input(state, "1", text, "user", TurnSignals())
    state.user_turns = 1
    store.save_state(state)
    return state


def ref(state):
    return (EvidenceRef(kind="user_turn", id=state.latest_turn_id, claim="测试用户原话"),)


def test_normal_words_are_not_interaction_boundaries(store):
    memory = MemoryService(store)
    state = state_and_turn(store, "我想下次先看看横轴和纵轴分别表示什么。")
    for text in (
        "我想下次先看看横轴和纵轴分别表示什么。",
        "我在分别给两个朋友回消息",
        "想识别问题在哪里",
        "个别同学还在说话",
    ):
        assert memory.explicit_boundary(text, state, state.latest_turn_id) is None
    for text in ("今天别问考试", "以后别主动给建议", "不要教我安排时间"):
        assert memory.explicit_boundary(text, state, state.latest_turn_id) is not None


def test_v2_16_scopes_expiry_reconnect_and_local_exception(store):
    now = [datetime(2026, 11, 3, 10, tzinfo=timezone.utc)]
    memory = MemoryService(store, "Asia/Shanghai", lambda: now[0])
    state = state_and_turn(store, "以后不要主动问论文")
    boundary = memory.explicit_boundary("以后不要主动问论文", state, state.latest_turn_id)
    assert memory.commit((boundary,), state, state.latest_turn_id)[0].startswith("accepted")
    other = state_and_turn(store, "今天可以问我论文进度", "s2")
    exception = memory.explicit_boundary("今天可以问我论文进度", other, other.latest_turn_id)
    memory.commit((exception,), other, other.latest_turn_id)
    assert not effective_boundaries(memory.retrieve(other, "论文"))
    now[0] += timedelta(days=1)
    boundaries = effective_boundaries(memory.retrieve(other, "论文"))
    assert len(boundaries) == 1 and boundaries[0].scope == "persistent"
    assert len(store.memory_items("u")) == 2


def test_v2_18_chinese_retrieval_complete_json_and_user_isolation(store):
    state = state_and_turn(store, "今天论文实验失败了")
    memory = MemoryService(store)
    candidate = MemoryCandidate(
        kind="episodic_event",
        key="论文实验",
        value="论文实验失败，需要重做",
        source_refs=ref(state),
        scope="persistent",
    )
    assert memory.commit((candidate,), state, state.latest_turn_id)[0].startswith("accepted")
    unrelated = state_and_turn(store, "另一个用户", "other", "someone_else")
    assert not memory.retrieve(unrelated, "论文实验").items
    bundle = memory.retrieve(state, "实验为什么失败")
    assert bundle.items and bundle.items[0].key == "论文实验"
    from companion.cognition.models import TurnPolicyFrame

    parsed = json.loads(prompt_projection(TurnPolicyFrame(memory_projection=bundle), 500))
    assert parsed["memory"][0]["source"]
    assert not memory.retrieve(state, "天气").items


def test_v2_11_older_memory_cannot_override_correction_and_supersedes_preserved(store):
    state = state_and_turn(store, "我叫小林")
    memory = MemoryService(store)
    original = MemoryCandidate(
        kind="fact_preference",
        key="nickname",
        value="小林",
        scope="persistent",
        source_refs=ref(state),
    )
    memory.commit((original,), state, state.latest_turn_id)
    previous = store.memory_items("u")[0]
    newer = state_and_turn(store, "我叫小琳，刚才记错了", "new")
    correction = original.model_copy(
        update={
            "value": "小琳",
            "source_refs": ref(newer),
            "supersedes_id": previous.memory_id,
            "expected_version": previous.version,
        }
    )
    assert memory.commit((correction,), newer, newer.latest_turn_id)[0].startswith("accepted")
    late = original.model_copy(update={"value": "小林旧值"})
    assert memory.commit((late,), state, state.latest_turn_id)[0].startswith("rejected")
    active = store.memory_items("u")
    assert (
        len(active) == 1
        and active[0].value == "小琳"
        and active[0].supersedes_id == previous.memory_id
    )


def test_v2_07_memory_quote_and_persistent_scope_need_user_evidence(store):
    state = state_and_turn(store, "这次先别给建议")
    memory = MemoryService(store)
    candidate = MemoryCandidate(
        kind="fact_preference",
        key="style",
        value="从不喜欢建议",
        scope="persistent",
        source_refs=ref(state),
    )
    assert memory.commit((candidate,), state, state.latest_turn_id)[0].startswith("rejected")
    forged = candidate.model_copy(
        update={
            "scope": "session",
            "source_refs": (
                EvidenceRef(
                    kind="user_turn", id=state.latest_turn_id, claim="假的", quote="不存在的原话"
                ),
            ),
        }
    )
    assert memory.commit((forged,), state, state.latest_turn_id)[0].startswith("rejected")


def test_v2_15_execution_does_not_create_positive_memory(store):
    state = state_and_turn(store, "今天有点累")
    memory = MemoryService(store)
    from companion.cognition.models import EventPayload, InteractionEvent

    event = InteractionEvent(
        event_id="e",
        idempotency_key="e",
        user_key="u",
        session_id="s",
        turn_id=state.latest_turn_id,
        event_type="playback_completed",
        origin="server_playback",
        payload=EventPayload(attribution="execution"),
    )
    assert store.record_interaction(event)
    assert not store.record_interaction(event)
    candidate = MemoryCandidate(
        kind="support_experience",
        key="benefit",
        value="很有效",
        scope="persistent",
        source_refs=(EvidenceRef(kind="interaction_event", id="e", claim="完成"),),
    )
    assert memory.commit((candidate,), state, state.latest_turn_id)[0].startswith("rejected")
    assert not store.memory_items("u")
