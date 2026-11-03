"""Validated boundary models and immutable conversation snapshots."""

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Stage(str, Enum):
    opening = "opening"
    explore = "explore"
    comfort = "comfort"
    permission = "permission"
    action = "action"
    closing = "closing"
    quiet = "quiet"


InputKind = Literal["user", "wake", "idle_end"]
Mode = Literal["normal", "exercise", "crisis"]
RiskLevel = Literal["none", "watch", "high"]
Pressure = Literal["academic", "social_evaluative", "relationship", "future", "self"]
Pathway = Literal["rumination", "self_criticism", "sleep", "loneliness"]
Level = Literal["low", "medium", "high"]


class TurnSignals(FrozenModel):
    emotion: str | None = None
    events: tuple[str, ...] = ()
    received_at: datetime = Field(default_factory=utcnow)


class RiskResult(FrozenModel):
    level: RiskLevel = "none"
    category: Literal["suicide", "self_harm", "abuse", "other"] = "other"
    reason: str = ""
    source: str = "lexicon"
    status: str = "ok"


class TypedConfidence(FrozenModel):
    type: Pressure
    confidence: float = Field(ge=0, le=1)


class SeekerState(FrozenModel):
    emotion_intensity: Level = "medium"
    trust: Level = "medium"
    initiative: Literal["student", "doll"] = "student"
    readiness: Level = "low"


class Assessment(FrozenModel):
    pressure_types: tuple[TypedConfidence, ...] = ()
    pathway_signals: tuple[Pathway, ...] = ()
    seeker_state: SeekerState = Field(default_factory=SeekerState)
    user_pref: Literal["listen", "solve", "unknown"] = "unknown"
    risk_level: Literal["none", "watch"] = "none"
    user_state: str = ""


class StageProposal(FrozenModel):
    to: Stage
    reason: str
    source_turn_ids: tuple[int, ...]


class CardEvidence(FrozenModel):
    card_id: str
    when_met: bool
    exclusions_present: bool
    source_turn_ids: tuple[int, ...]


class CardSelection(FrozenModel):
    allowed: tuple[str, ...] = ()
    preferred: str | None = None
    evidence: tuple[CardEvidence, ...] = ()


class ProfileUpdate(FrozenModel):
    field: Literal["nickname", "important_people", "interests", "effective_comfort", "notes"]
    value: str
    source_turn_ids: tuple[int, ...]


class MemoryEvent(FrozenModel):
    summary: str
    pressure_type: Pressure
    date: str | None = None
    importance: int = Field(default=5, ge=1, le=10)
    source_turn_ids: tuple[int, ...]


class Followup(FrozenModel):
    kind: Literal["event", "action", "experiment"] = "event"
    content: str
    due_date: str
    importance: int = Field(default=5, ge=1, le=10)
    source_turn_ids: tuple[int, ...]


class FollowupResult(FrozenModel):
    followup_id: int
    result: str
    source_turn_ids: tuple[int, ...]


class MemoryUpdate(FrozenModel):
    profile_updates: tuple[ProfileUpdate, ...] = ()
    events: tuple[MemoryEvent, ...] = ()
    followups: tuple[Followup, ...] = ()
    followup_results: tuple[FollowupResult, ...] = ()


class ReasonerOutput(FrozenModel):
    assessment: Assessment = Field(default_factory=Assessment)
    stage_proposal: StageProposal | None = None
    cards: CardSelection = Field(default_factory=CardSelection)
    offer_exercise: bool = False
    topic_changed: bool = False
    memory: MemoryUpdate = Field(default_factory=MemoryUpdate)
    session_summary: str | None = None


class CoreMemory(FrozenModel):
    profile_brief: str = ""
    active_stressors: tuple[str, ...] = ()
    followups_due: tuple[str, ...] = ()
    last_session_summary: str = ""


class Snapshot(FrozenModel):
    session_id: str
    user_key: str
    version: int = 0
    source_turn_id: int = 0
    created_at: datetime = Field(default_factory=utcnow)
    trigger: str = "initial"
    assessment: Assessment = Field(default_factory=Assessment)
    stage_proposal: StageProposal | None = None
    allowed_cards: tuple[str, ...] = ()
    preferred_card: str | None = None
    offer_exercise: bool = False
    core_memory: CoreMemory = Field(default_factory=CoreMemory)
    topic_changed: bool = False


class PendingOffer(BaseModel):
    offer_id: str
    kind: Literal["action", "exercise", "resume_exercise"]
    target_id: str | None = None
    topic_revision: int
    offered_turn_id: int
    offered_user_index: int
    active: bool = False
    status: Literal["awaiting_consent", "accepted_waiting_card", "ready"] = "awaiting_consent"
    accepted_at: float | None = None
    accepted_user_index: int | None = None


class SessionState(BaseModel):
    session_id: str
    user_key: str
    lifecycle: Literal["active", "ending", "closed"] = "active"
    stage: Stage = Stage.opening
    mode: Mode = "normal"
    state_revision: int = 0
    topic_revision: int = 0
    generation: int = 0
    latest_turn_id: int = 0
    user_turns: int = 0
    last_reasoner_user_index: int = 0
    applied_snapshot_version: int = 0
    pending_offer: PendingOffer | None = None
    action_id: str | None = None
    card_in_use: str | None = None
    action_turns: int = 0
    cards_used: dict[str, int] = Field(default_factory=dict)
    cards_refused: set[str] = Field(default_factory=set)
    permission_asked_topic: int | None = None
    rest_reminded: bool = False
    active_plan_id: str | None = None
    resume_script_id: str | None = None
    resume_index: int = 0
    crisis_turns: int = 0
    closing_turns: int = 0
    started_at: datetime = Field(default_factory=utcnow)
    started_mono: float = 0


class TurnContext(FrozenModel):
    session_id: str
    turn_id: int
    generation: int
    text: str
    kind: InputKind
    stage: Stage
    mode: Mode
    card_id: str | None = None
    snapshot: Snapshot
    signals: TurnSignals
    trigger_reasons: tuple[str, ...] = ()
    directive: str | None = None
    t0: float


class PlaybackSegment(FrozenModel):
    text: str
    pause_s: float = Field(default=0, ge=0, le=30)
    audio_path: str | None = None
    audio_duration_s: float | None = Field(default=None, ge=0)


class PlaybackPlan(FrozenModel):
    script_id: str
    segments: tuple[PlaybackSegment, ...]
    start_index: int = 0
    measured: bool = False


class OutputEvent(FrozenModel):
    output_id: str
    session_id: str
    turn_id: int
    generation: int
    type: Literal["text", "exercise_plan", "crisis_plan"] = "text"
    text: str = ""
    emoji: str = "😶"
    plan: PlaybackPlan | None = None
    purpose: str = "reply"
    offer_id: str | None = None
    followup_id: int | None = None
    template_version: str | None = None


class PlaybackEvent(FrozenModel):
    output_id: str
    session_id: str
    generation: int
    status: Literal["started", "completed", "cancelled", "failed", "segment"]
    segment_index: int | None = None
    error: str | None = None
    at: datetime = Field(default_factory=utcnow)


class ReasonerTask(FrozenModel):
    session_id: str
    user_key: str
    kind: Literal["normal", "end"]
    trigger_reasons: tuple[str, ...]
    source_turn_id: int
    state_revision: int
    topic_revision: int
    base_snapshot_version: int
    user_index: int


class Rejection(FrozenModel):
    rule: str
    detail: str


class RuleResult(FrozenModel):
    fired_rules: tuple[str, ...] = ()
    trigger_reasons: tuple[str, ...] = ()
    directive: str | None = None
