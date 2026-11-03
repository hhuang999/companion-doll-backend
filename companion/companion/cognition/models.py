"""Model-owned candidates are distinct from server-owned publication metadata."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from companion.memory.models import MemoryBundle, MemoryCandidate

from .base import Contract, EvidenceRef, utcnow

Objective = Literal[
    "listen",
    "clarify",
    "comfort",
    "reflect",
    "provide_information",
    "invite_action",
    "invite_exercise",
    "close",
    "quiet",
]
JobKind = Literal["routine", "deliberation", "memory", "end_consolidation"]
JobStatus = Literal[
    "queued",
    "running",
    "completed",
    "partial",
    "rejected",
    "failed",
    "timed_out",
    "cancelled",
    "superseded",
    "interrupted",
    "expired",
]


class Fact(Contract):
    statement: str = Field(max_length=240)
    evidence: tuple[EvidenceRef, ...] = Field(min_length=1, max_length=4)


class Hypothesis(Fact):
    conflicting_evidence: tuple[EvidenceRef, ...] = ()


class OpenQuestion(Contract):
    question: str = Field(max_length=160)
    ask_now: bool = False


class SituationAssessment(Contract):
    facts: tuple[Fact, ...] = Field(default=(), max_length=5)
    hypotheses: tuple[Hypothesis, ...] = Field(default=(), max_length=3)
    expressed_need: Literal["listen", "clarify", "comfort", "solve", "quiet", "unknown"] = "unknown"
    open_questions: tuple[OpenQuestion, ...] = Field(default=(), max_length=2)
    topic_summary: str = Field(default="", max_length=240)
    topic_change_proposal: bool = False
    boundary_candidates: tuple[MemoryCandidate, ...] = Field(default=(), max_length=3)
    memory_candidates: tuple[MemoryCandidate, ...] = Field(default=(), max_length=5)
    risk_review_requested: bool = False
    pressure_types: tuple[
        Literal["academic", "social_evaluative", "relationship", "future", "self"], ...
    ] = ()
    pathway_signals: tuple[Literal["rumination", "self_criticism", "sleep", "loneliness"], ...] = ()
    emotion_intensity: Literal["low", "medium", "high"] = "medium"
    readiness: Literal["low", "medium", "high"] = "low"


class CandidateAction(Contract):
    action_id: str
    kind: Literal["card", "exercise"] = "card"
    evidence: tuple[EvidenceRef, ...] = Field(min_length=1, max_length=4)
    requires_permission: Literal[True] = True
    when_met: bool
    exclusions_present: bool


class Avoid(Contract):
    kind: Literal["no_advice", "no_repeat_offer", "no_topic_probe", "no_memory_mention"]
    target: str | None = None
    scope: Literal["turn", "topic", "session"] = "topic"


class PlanCandidate(Contract):
    objective: Objective
    understanding: str = Field(max_length=240)
    evidence: tuple[EvidenceRef, ...] = Field(min_length=1, max_length=6)
    response_guidance: tuple[str, ...] = Field(default=(), max_length=3)
    open_question: str | None = Field(default=None, max_length=160)
    candidate_actions: tuple[CandidateAction, ...] = Field(default=(), max_length=2)
    avoid: tuple[Avoid, ...] = Field(default=(), max_length=6)
    observation_targets: tuple[str, ...] = Field(default=(), max_length=3)


class SupportPlan(PlanCandidate):
    schema_version: Literal[2] = 2
    plan_id: str
    version: int = Field(ge=1)
    candidate_version: int = Field(ge=1, le=2)
    user_key: str
    session_id: str
    topic_revision: int
    source_turn_id: int
    source_user_index: int
    checked_through_user_index: int
    policy_revision: int
    base_plan_version: int
    boundary_revision: int
    memory_dependency_versions: tuple[tuple[str, int], ...] = ()
    created_at: datetime = Field(default_factory=utcnow)
    valid_until: datetime
    max_user_turn_delta: int = 4
    review_status: Literal["not_required", "approved", "rejected", "incomplete"]
    review_run_id: str | None = None
    status: Literal["active", "superseded", "invalidated", "expired"] = "active"


class ReviewBrief(Contract):
    concerns: tuple[Fact, ...] = Field(default=(), max_length=3)
    counter_evidence: tuple[EvidenceRef, ...] = Field(default=(), max_length=3)


class ReviewIssue(Contract):
    code: Literal[
        "unsupported_fact",
        "intent_mismatch",
        "refusal_ignored",
        "consent_missing",
        "memory_conflict",
        "premature_advice",
        "repeated_advice",
        "persona_boundary",
        "card_ineligible",
    ]
    severity: Literal["warning", "blocking"]
    evidence_refs: tuple[EvidenceRef, ...] = ()
    explanation: str = Field(max_length=240)


class ReviewResult(Contract):
    candidate_id: str
    candidate_version: int = Field(ge=1, le=2)
    verdict: Literal["approve", "revise", "reject", "insufficient_information"]
    issues: tuple[ReviewIssue, ...] = Field(default=(), max_length=6)
    required_changes: tuple[str, ...] = Field(default=(), max_length=3)
    unresolved_questions: tuple[str, ...] = Field(default=(), max_length=2)


class DeltaResult(Contract):
    verdict: Literal["compatible", "invalidate", "uncertain"]
    evidence: tuple[EvidenceRef, ...] = Field(min_length=1, max_length=4)
    reason: str = Field(max_length=240)


class Consolidation(Contract):
    memory_candidates: tuple[MemoryCandidate, ...] = Field(default=(), max_length=6)
    summary: str | None = Field(default=None, max_length=400)
    followups: tuple["FollowupCandidate", ...] = Field(default=(), max_length=2)


class FollowupCandidate(Contract):
    content: str = Field(max_length=200)
    due_date: str
    importance: int = Field(default=5, ge=1, le=10)
    evidence: tuple[EvidenceRef, ...] = Field(min_length=1, max_length=3)


Consolidation.model_rebuild()


class EventPayload(Contract):
    text: str | None = Field(default=None, max_length=500)
    target: str | None = None
    attribution: Literal["explicit", "unattributed", "execution"] = "unattributed"
    valence: Literal["positive", "negative", "unknown"] = "unknown"
    action_id: str | None = None
    scope: str | None = None
    detail: str | None = Field(default=None, max_length=300)


class InteractionEvent(Contract):
    schema_version: Literal[2] = 2
    event_id: str
    idempotency_key: str
    user_key: str
    session_id: str
    turn_id: int | None = None
    output_id: str | None = None
    offer_id: str | None = None
    support_plan_id: str | None = None
    event_type: Literal[
        "user_correction",
        "support_refused",
        "boundary_requested",
        "topic_changed",
        "explicit_feedback",
        "offer_accepted",
        "offer_withdrawn",
        "playback_started",
        "playback_completed",
        "playback_cancelled",
        "playback_failed",
        "exercise_completed",
        "exercise_interrupted",
        "session_ended",
        "control_uncertain",
    ]
    origin: Literal[
        "user_explicit", "deterministic_rule", "semantic_candidate", "server_playback", "device_ack"
    ]
    payload: EventPayload = Field(default_factory=EventPayload)
    evidence: tuple[EvidenceRef, ...] = ()
    occurred_at: datetime = Field(default_factory=utcnow)
    recorded_at: datetime = Field(default_factory=utcnow)


class TurnPolicyFrame(Contract):
    effective_support_plan_id: str | None = None
    effective_support_plan_version: int | None = None
    objective: Objective = "listen"
    response_guidance: tuple[str, ...] = ()
    avoid: tuple[Avoid, ...] = ()
    open_question: str | None = None
    active_boundaries: tuple[MemoryCandidate, ...] = ()
    allowed_action_ids: tuple[str, ...] = ()
    memory_projection: MemoryBundle = Field(default_factory=MemoryBundle)
    selection_reason: str = "safe_default"
    checked_through_user_index: int = 0


class CognitiveJob(Contract):
    schema_version: Literal[2] = 2
    job_id: str
    user_key: str
    session_id: str
    kind: JobKind
    triggers: tuple[str, ...]
    source_turn_id: int
    source_user_index: int
    topic_revision: int
    policy_revision: int
    boundary_revision: int
    base_plan_version: int
    epoch: int = 0
    priority: int = 3
    status: JobStatus = "queued"
    attempt: int = 1
    retry_of: str | None = None
    queued_at: datetime = Field(default_factory=utcnow)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    budget_limits: dict[str, int | float] = Field(default_factory=dict)


class Usage(Contract):
    input_tokens: int | None = None
    output_tokens: int | None = None
    source: Literal["provider", "estimated", "unknown"] = "unknown"


class PublicationResult(Contract):
    plan: str = "not_produced"
    memory: tuple[str, ...] = ()
    summary: str = "not_produced"
    status: JobStatus
