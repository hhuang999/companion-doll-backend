import json
from collections import deque

import pytest
from companion.adapters.output import RecordingOutputPort
from companion.core.api import CompanionCore
from companion.core.models import TurnSignals
from companion.llm.fake import FakeLLM


@pytest.fixture
def engine(config, store):
    fake = FakeLLM()
    core = CompanionCore(config, store, fake)
    core.bind_output("s", "u", RecordingOutputPort(core.on_playback_event))
    yield core, fake, store
    for event in fake.role_releases.values():
        event.set()
    core.close()


def proposal(key="工作时间", value="早上9点至下午5点", scope="persistent", followup=False):
    def make(payload):
        source = next(row for row in reversed(payload["history"]) if row["role"] == "user")
        reference = {"kind": "user_turn", "id": source["id"], "claim": key, "quote": source["text"]}
        return {
            "memory_candidates": [
                {
                    "kind": "fact_preference",
                    "key": key,
                    "value": value,
                    "scope": scope,
                    "source_refs": [reference],
                }
            ],
            "summary_evidence": [reference],
            "followups": [
                {"content": "询问工作情况", "due_date": payload["today"], "evidence": [reference]}
            ]
            if followup
            else [],
        }

    return make


def decisions(verdict):
    return lambda p: {
        "decisions": [
            {
                "kind": item["kind"],
                "index": item["index"],
                "verdict": verdict,
                "reason": "测试语义支持结论",
            }
            for item in p["claims"]
        ]
    }


def finish(engine, text):
    core, _, store = engine
    core.on_input("s", "1", text, TurnSignals())
    core.on_session_end("s", "test")
    assert core.wait_idle()
    assert store.query("SELECT status FROM end_tasks")[0]["status"] == "done"
    return store.query("SELECT summary FROM sessions")[0]["summary"]


@pytest.mark.parametrize("scope", ["session", "persistent"])
@pytest.mark.parametrize("text", ["早上9点至下午5点。", "早上9点至下午5点。以后再聊。"])
def test_invented_activity_is_filtered_regardless_of_scope_or_keywords(engine, scope, text):
    core, fake, store = engine
    fake.roles["end"] = deque([proposal(scope=scope, followup=True)])
    fake.roles["memory"] = deque([decisions("not_enough_information")])
    summary = finish(engine, text)
    assert not store.memory_items("u")
    assert not store.query("SELECT * FROM followups")
    assert "工作" not in summary and text in summary
    result = json.loads(store.query("SELECT result FROM cognitive_jobs")[0]["result"])
    assert result["consolidation_review"]["status"] == "filtered"
    assert result["budget"]["calls"] == 2
    assert core.sessions == {}


def test_explicit_personal_fact_can_persist_without_magic_words(engine):
    _, fake, store = engine
    fake.roles["end"] = deque([proposal(key="就读情况", value="在广州读高中")])
    fake.roles["memory"] = deque([decisions("entailed")])
    finish(engine, "我在广州读高中。")
    item = store.memory_items("u")[0]
    assert item.scope == "persistent" and item.value == "在广州读高中"
    assert item.source_refs[0].quote == "我在广州读高中。"


def test_temporary_refusal_is_not_promoted_to_a_persistent_preference(engine):
    _, fake, store = engine
    fake.roles["end"] = deque([proposal(key="回应偏好", value="从不需要建议")])
    fake.roles["memory"] = deque([decisions("not_enough_information")])
    finish(engine, "这次先别给建议。")
    assert not any(item.scope == "persistent" for item in store.memory_items("u"))


@pytest.mark.parametrize("error", [TimeoutError("review timeout"), ValueError("invalid review")])
def test_unavailable_review_closes_with_quotes_and_no_unverified_claims(engine, error):
    _, fake, store = engine
    fake.roles["end"] = deque([proposal(followup=True)])
    fake.roles["memory"] = deque([error])
    summary = finish(engine, "早上9点至下午5点。")
    assert "早上9点至下午5点" in summary and "工作" not in summary
    assert not store.memory_items("u") and not store.query("SELECT * FROM followups")
    result = json.loads(store.query("SELECT result FROM cognitive_jobs")[0]["result"])
    assert result["consolidation_review"]["status"] == "unavailable"
    assert result["budget"]["calls"] <= 2


@pytest.mark.parametrize(
    "review",
    [
        {"decisions": []},
        {
            "decisions": [
                {"kind": "memory", "index": 1, "verdict": "entailed", "reason": "错位候选"}
            ]
        },
    ],
)
def test_missing_or_wrong_review_indices_cannot_approve_a_candidate(engine, review):
    _, fake, store = engine
    fake.roles["end"] = deque([proposal()])
    fake.roles["memory"] = deque([review])
    finish(engine, "早上9点至下午5点。")
    assert not store.memory_items("u")
    result = json.loads(store.query("SELECT result FROM cognitive_jobs")[0]["result"])
    assert result["consolidation_review"]["status"] == "unavailable"


def test_primary_repair_consumes_budget_without_allowing_unreviewed_memory(engine):
    _, fake, store = engine
    fake.roles["end"] = deque(
        [
            {
                "summary_evidence": [
                    {"kind": "user_turn", "id": 999, "claim": "错误来源", "quote": "不存在"}
                ]
            },
            proposal(),
        ]
    )
    summary = finish(engine, "早上9点至下午5点。")
    assert "工作" not in summary and not store.memory_items("u")
    result = json.loads(store.query("SELECT result FROM cognitive_jobs")[0]["result"])
    assert result["budget"]["calls"] == 2
    assert result["budget"]["schema_repairs"] == 1
    assert not [r for r in fake.requests if r["payload"].get("phase") == "grounding"]


def test_summary_is_built_from_quotes_not_model_claim_labels(engine):
    _, fake, _ = engine
    fake.roles["end"] = deque(
        [
            lambda p: {
                "summary_evidence": [
                    {
                        "kind": "user_turn",
                        "id": p["final_turn_id"],
                        "claim": "用户工作时间",
                        "quote": "早上9点至下午5点。",
                    }
                ]
            }
        ]
    )
    summary = finish(engine, "早上9点至下午5点。")
    assert summary == "用户原话：“早上9点至下午5点。”"
    assert len(fake.requests) == 1


def test_missing_quotes_are_bound_without_spending_a_repair_call(engine):
    _, fake, store = engine

    def without_quotes(payload):
        result = proposal(key="就读情况", value="在广州读高中")(payload)
        result["memory_candidates"][0]["source_refs"][0].pop("quote")
        result["summary_evidence"][0].pop("quote", None)
        return result

    fake.roles["end"] = deque([without_quotes])
    summary = finish(engine, "我在广州读高中。")
    assert "我在广州读高中。" in summary
    assert store.memory_items("u")[0].source_refs[0].quote == "我在广州读高中。"
    result = json.loads(store.query("SELECT result FROM cognitive_jobs")[0]["result"])
    assert result["budget"]["calls"] == 2 and result["budget"]["schema_repairs"] == 0


def test_review_uses_cited_sources_not_extractor_rationales_or_retention_metadata(engine):
    core, fake, store = engine
    core.config.settings.cognition.critic_model = "source-review-model"
    core.on_input("s", "earlier", "我在广州读高中。", TurnSignals())
    seen = []

    def extraction(payload):
        result = proposal()(payload)
        result["memory_candidates"][0]["source_refs"][0]["claim"] = "模型断言已获用户确认"
        return result

    def review(payload):
        seen.append(payload)
        return decisions("not_enough_information")(payload)

    fake.roles["end"] = deque([extraction])
    fake.roles["memory"] = deque([review])
    finish(engine, "早上9点至下午5点。")
    assert [row["text"] for row in seen[0]["history"]] == ["早上9点至下午5点。"]
    serialized = json.dumps(seen[0], ensure_ascii=False)
    assert "模型断言已获用户确认" not in serialized and "persistent" not in serialized
    assert seen[0]["claims"][0]["hypothesis"] == "用户的工作时间是早上9点至下午5点。"
    assert store.query("SELECT model FROM agent_runs WHERE role='memory'") == [
        {"model": "source-review-model"}
    ]
