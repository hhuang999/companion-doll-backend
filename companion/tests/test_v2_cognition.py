import json
import threading
from datetime import timedelta

import pytest
from companion.adapters.output import RecordingOutputPort
from companion.cognition.base import EvidenceRef
from companion.cognition.budget import Budget, BudgetExceeded
from companion.cognition.models import SituationAssessment, Usage
from companion.core.api import CompanionCore
from companion.core.config import JobBudgetSettings
from companion.core.models import TurnSignals
from companion.llm.fake import FakeLLM
from companion.memory.models import MemoryCandidate


@pytest.fixture
def engine(config, store):
    fake = FakeLLM()
    core = CompanionCore(config, store, fake)
    port = RecordingOutputPort(core.on_playback_event)
    core.bind_output("s", "u", port)
    yield core, fake, port
    for event in fake.role_releases.values():
        event.set()
    if fake.reasoner_release:
        fake.reasoner_release.set()
    core.close()


def input_turn(core, text, key=None, session="s", respond=True):
    import uuid

    turn = core.on_input(session, key or uuid.uuid4().hex, text, TurnSignals())
    if respond:
        for event in core.respond(session, turn):
            core.dispatch(event)
    return turn


def start_role(fake, role):
    fake.role_started.setdefault(role, threading.Event())
    fake.role_releases[role] = threading.Event()
    return fake.role_started[role], fake.role_releases[role]


def test_v2_01_blocked_background_does_not_block_talker(engine):
    core, fake, port = engine
    started, release = start_role(fake, "analysis")
    input_turn(core, "这件事反复困扰我，怎么办")
    assert started.wait(2)
    input_turn(core, "今天老师发下试卷的时候我很难过")
    assert port.events
    assert core.store.query("SELECT status FROM cognitive_jobs WHERE status='running'")
    assert not core.store.query("SELECT * FROM support_plans")
    release.set()
    assert core.wait_idle()


def test_v2_02_periodic_trigger_and_merge(engine):
    core, fake, _ = engine
    for n in range(3):
        input_turn(core, f"普通倾诉第{n}轮")
    assert not core.store.query("SELECT * FROM cognitive_jobs")
    started, release = start_role(fake, "analysis")
    input_turn(core, "第四轮普通倾诉")
    assert started.wait(2)
    core.reasoner.submit("u", "s", "periodic")
    core.reasoner.submit("u", "s", "topic_changed")
    assert len(core.reasoner.pending) == 1
    assert core.store.query("SELECT * FROM cognitive_jobs WHERE status='superseded'")
    release.set()
    assert core.wait_idle()


def test_v2_04_independent_brief_exact_version_single_revision(engine):
    core, fake, _ = engine
    from collections import deque

    fake.roles["critic"] = deque(
        [
            lambda p: {
                "candidate_id": p["candidate_id"],
                "candidate_version": 1,
                "verdict": "revise",
                "required_changes": ["更简短"],
            },
            lambda p: {
                "candidate_id": p["candidate_id"],
                "candidate_version": 2,
                "verdict": "approve",
            },
        ]
    )
    input_turn(core, "这件事反复困扰我，怎么办")
    assert core.wait_idle()
    brief = next(r["payload"] for r in fake.requests if r["role"] == "brief")
    assert not {"analysis", "candidate", "cards"}.intersection(brief)
    plan = core.store.active_support_plan("s")
    assert plan and plan.review_status == "approved" and plan.candidate_version == 2
    review = core.store.query(
        "SELECT result FROM agent_runs WHERE run_id=?", (plan.review_run_id,)
    )[0]
    assert json.loads(review["result"])["candidate_version"] == 2
    assert len([r for r in fake.requests if r["role"] == "planner"]) == 2


def test_server_constraint_conflict_requires_revision_and_exact_recheck(engine):
    from collections import deque

    core, fake, _ = engine

    def candidate(payload):
        user = next(row for row in reversed(payload["history"]) if row["role"] == "user")
        return {
            "objective": "clarify",
            "understanding": "合成约束冲突",
            "evidence": [{"kind": "user_turn", "id": user["id"], "claim": "原话"}],
            "open_question": None if "previous_candidate" in payload else "你想说说吗？",
            "avoid": [{"kind": "no_topic_probe", "target": None}],
        }

    fake.roles["planner"] = deque([candidate, candidate])
    input_turn(core, "这件事反复困扰我，怎么办")
    assert core.wait_idle()
    plan = core.store.active_support_plan("s")
    assert plan and plan.candidate_version == 2 and plan.open_question is None
    reviews = [row for row in fake.requests if row["role"] == "critic"]
    assert len(reviews) == 2 and reviews[0]["payload"]["server_checks"]
    assert not reviews[1]["payload"]["server_checks"]


def test_v2_05_revision_without_recheck_never_publishes(engine):
    core, fake, _ = engine
    from collections import deque

    fake.roles["critic"] = deque(
        [
            lambda p: {
                "candidate_id": p["candidate_id"],
                "candidate_version": 1,
                "verdict": "revise",
            },
            TimeoutError("injected review timeout"),
        ]
    )
    input_turn(core, "怎么办")
    assert core.wait_idle()
    assert not core.store.active_support_plan("s")
    assert core.store.query("SELECT status FROM cognitive_jobs")[0]["status"] == "timed_out"


def test_end_evidence_repair_keeps_invalid_memory_out_of_store(engine):
    from collections import deque

    core, fake, _ = engine
    input_turn(core, "今天想聊聊考试")
    fake.roles["end"] = deque(
        [
            {
                "memory_candidates": [
                    {
                        "kind": "episodic_event",
                        "key": "invalid",
                        "value": "未经提供的来源",
                        "source_refs": [
                            {"kind": "interaction_event", "id": "not-in-input", "claim": "错误来源"}
                        ],
                    }
                ],
                "summary": "错误",
            },
            {"memory_candidates": [], "summary": "用户想聊考试。"},
        ]
    )
    core.on_session_end("s", "test")
    assert core.wait_idle()
    assert core.store.query("SELECT status FROM end_tasks")[0]["status"] == "done"
    assert not core.store.query("SELECT * FROM memory_items WHERE key='invalid'")
    runs = core.store.query("SELECT status,error FROM agent_runs WHERE role='end' ORDER BY attempt")
    assert [r["status"] for r in runs] == ["schema_error", "completed"]
    assert "EvidenceValidationError" in runs[0]["error"]


def test_blocked_invitation_cannot_become_unconsented_talker_advice(engine):
    core, fake, port = engine
    input_turn(core, "不要告诉我必须选哪个专业")
    fake.streams.append("从一个小问题开始试试。")
    input_turn(core, "有什么办法能从一个小问题开始吗？")
    assert core.sessions["s"].state.pending_offer is None
    assert port.events[-1].text == core.config.stages["templates"]["boundary_hold"]
    assert "试试" not in port.events[-1].text


def test_v2_06_budget_reservations_deadline_shared_repair():
    clock = [0.0]
    budget = Budget(
        JobBudgetSettings(max_calls=2, output_tokens=200, total_tokens=600),
        20,
        threading.Event(),
        lambda: clock[0],
    )
    budget.reserve(100, 100)
    budget.settle(100, 100, Usage(input_tokens=90, output_tokens=40, source="provider"))
    budget.reserve(100, 100, repair=True)
    with pytest.raises(BudgetExceeded):
        budget.reserve(1, 1, repair=True)
    clock[0] = 21
    with pytest.raises(TimeoutError):
        budget.check()


def test_schema_repair_uses_remaining_output_without_raising_job_limit():
    budget = Budget(
        JobBudgetSettings(max_calls=2, output_tokens=1800, total_tokens=6000),
        20,
        threading.Event(),
    )
    first = budget.reserve(1000, 1800, allow_partial=True)
    budget.settle(1000, first, Usage(input_tokens=1000, output_tokens=300, source="provider"))
    repair = budget.reserve(1100, 1800, repair=True, allow_partial=True)
    assert repair == 1500
    assert budget.report()["accounted_output_tokens"] == 1800
    with pytest.raises(BudgetExceeded):
        budget.reserve(1, 128, allow_partial=True)


def test_v2_07_foreign_evidence_and_forged_memory_rejected(engine):
    core, fake, _ = engine
    from collections import deque

    fake.roles["analysis"] = deque(
        [
            {
                "facts": [
                    {
                        "statement": "假事实",
                        "evidence": [{"kind": "memory", "id": "forged", "claim": "假的"}],
                    }
                ]
            }
        ]
    )
    input_turn(core, "怎么办")
    assert core.wait_idle()
    assert not core.store.active_support_plan("s")
    assert core.store.query("SELECT status FROM cognitive_jobs")[0]["status"] == "rejected"


def test_v2_08_ordinary_new_input_is_guarded_and_published(engine):
    core, fake, _ = engine
    started, release = start_role(fake, "analysis")
    input_turn(core, "今天有点累", respond=False)
    core.reasoner.submit("u", "s", "periodic")
    assert started.wait(2)
    input_turn(core, "主要是事情太多", respond=False)
    release.set()
    assert core.wait_idle()
    plan = core.store.active_support_plan("s")
    assert plan and plan.source_user_index == 1 and plan.checked_through_user_index == 2
    assert "delta" in fake.calls


def test_v2_09_delta_guard_final_cas_rejects_newer_input(engine):
    core, fake, _ = engine
    analysis_started, analysis_release = start_role(fake, "analysis")
    delta_started, delta_release = start_role(fake, "delta")
    input_turn(core, "普通倾诉", respond=False)
    core.reasoner.submit("u", "s", "periodic")
    assert analysis_started.wait(2)
    input_turn(core, "再补充一点", respond=False)
    analysis_release.set()
    assert delta_started.wait(2)
    input_turn(core, "还有一件事", respond=False)
    delta_release.set()
    assert core.wait_idle()
    assert not core.store.active_support_plan("s")
    job = core.store.query("SELECT status,result FROM cognitive_jobs")[0]
    assert job["status"] == "superseded" and "final_cas_conflict" in job["result"]
    assert fake.calls.count("delta") == 1


def test_v2_10_plan_expiry_does_not_refresh_on_read(engine):
    core, _, _ = engine
    input_turn(core, "普通倾诉")
    core.reasoner.submit("u", "s", "periodic")
    assert core.wait_idle()
    plan = core.store.active_support_plan("s")
    from companion.cognition.policy import plan_invalid_reason

    now = plan.valid_until + timedelta(seconds=1)
    assert (
        plan_invalid_reason(plan, core.sessions["s"].state, core.store.revisions("u"), [], now)
        == "expired"
    )
    assert core.store.active_support_plan("s").valid_until == plan.valid_until


def test_v2_12_plan_expired_independent_memory_commits_partial(engine):
    core, fake, _ = engine
    from collections import deque

    def assessment(p):
        tid = [r["id"] for r in p["history"] if r["role"] == "user"][-1]
        core.config.settings.cognition.plan_ttl_s = 0.000001
        return SituationAssessment(
            memory_candidates=(
                MemoryCandidate(
                    kind="episodic_event",
                    key="exam",
                    value="今天参加考试",
                    scope="persistent",
                    source_refs=(EvidenceRef(kind="user_turn", id=tid, claim="用户原话"),),
                ),
            )
        )

    fake.roles["analysis"] = deque([assessment])
    input_turn(core, "今天参加考试")
    core.reasoner.submit("u", "s", "periodic")
    assert core.wait_idle()
    assert core.store.memory_items("u")
    assert not core.store.active_support_plan("s")
    assert core.store.query("SELECT status FROM cognitive_jobs")[0]["status"] == "partial"


def test_v2_14_risk_high_bypasses_busy_background(engine):
    core, fake, port = engine
    started, release = start_role(fake, "analysis")
    input_turn(core, "怎么办")
    assert started.wait(2)
    input_turn(core, "我想自杀")
    assert port.events[-1].type == "crisis_plan"
    assert core.sessions["s"].state.mode == "crisis"
    release.set()
    assert core.wait_idle()
    assert not core.store.active_support_plan("s")


def test_v2_21_purge_waits_inflight_and_does_not_resurrect(engine):
    core, fake, _ = engine
    started, release = start_role(fake, "analysis")
    input_turn(core, "怎么办")
    assert started.wait(2)
    done = threading.Event()
    thread = threading.Thread(target=lambda: (core.purge_user("u"), done.set()))
    thread.start()
    release.set()
    assert done.wait(5)
    thread.join()
    for table in (
        "users",
        "sessions",
        "turns",
        "cognitive_jobs",
        "agent_runs",
        "support_plans",
        "memory_items",
        "interaction_events",
    ):
        assert not core.store.query(f"SELECT * FROM {table}")


def test_v2_11_plan_memory_dependency_conflict_across_sessions(engine):
    core, fake, _ = engine
    from collections import deque

    from companion.core.models import SessionState

    input_turn(core, "我叫小林")
    old = core.store.memory_items("u")[0]
    started, release = start_role(fake, "planner")
    fake.roles["planner"] = deque(
        [
            {
                "objective": "listen",
                "understanding": "称呼用户",
                "evidence": [{"kind": "memory", "id": old.memory_id, "claim": "称呼依据"}],
            }
        ]
    )
    core.reasoner.submit("u", "s", "periodic")
    assert started.wait(2)
    other = SessionState(session_id="other", user_key="u")
    core.store.create_session(other)
    tid = core.store.add_input(other, "new", "我叫小琳", "user", TurnSignals())
    candidate = MemoryCandidate(
        kind="fact_preference",
        key="nickname",
        value="小琳",
        scope="persistent",
        source_refs=(EvidenceRef(kind="user_turn", id=tid, claim="更正"),),
        supersedes_id=old.memory_id,
        expected_version=old.version,
    )
    core.cognition.memory.commit((candidate,), other, tid)
    release.set()
    assert core.wait_idle()
    assert not core.store.active_support_plan("s")
    assert core.store.memory_items("u")[0].value == "小琳"


def test_v2_05_wrong_review_version_cannot_publish(engine):
    core, fake, _ = engine
    from collections import deque

    fake.roles["critic"] = deque(
        [
            lambda p: {
                "candidate_id": p["candidate_id"],
                "candidate_version": 2,
                "verdict": "approve",
            }
        ]
    )
    input_turn(core, "怎么办")
    assert core.wait_idle()
    assert not core.store.active_support_plan("s")
    assert "mismatch" in core.store.query("SELECT error FROM cognitive_jobs")[0]["error"]


def test_v2_06_provider_failure_is_visible_without_retry(engine):
    core, fake, _ = engine
    from collections import deque

    fake.roles["analysis"] = deque([RuntimeError("synthetic upstream 429")])
    input_turn(core, "普通倾诉")
    core.reasoner.submit("u", "s", "periodic")
    assert core.wait_idle()
    assert core.store.query("SELECT status FROM cognitive_jobs")[0]["status"] == "failed"
    assert fake.calls.count("analysis") == 1
