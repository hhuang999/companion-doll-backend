"""Content evidence is separate from a runtime Critic's approval."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ContentModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class StrategyProtocol(ContentModel):
    version: str = Field(min_length=1)
    mechanism: str = Field(min_length=1)
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    adaptation: str = Field(min_length=1)
    minimum_information: tuple[str, ...] = Field(min_length=1)
    prerequisites: tuple[str, ...] = Field(min_length=1)
    required_contexts: tuple[str, ...] = ()
    excluded_contexts: tuple[str, ...] = ()
    burden: str = Field(min_length=1)
    permission: str = Field(min_length=1)
    stop: str = Field(min_length=1)
    followup: str = Field(min_length=1)
    feedback_limits: str = Field(min_length=1)
    counterexample: str = Field(min_length=1)
    keywords: tuple[str, ...] = ()
    legacy_ids: tuple[str, ...] = ()


class ExerciseProtocol(ContentModel):
    version: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    prerequisites: tuple[str, ...] = Field(min_length=1)
    required_contexts: tuple[str, ...] = ()
    excluded_contexts: tuple[str, ...] = ()
    pathways: tuple[str, ...] = ()
    request_phrases: tuple[str, ...] = ()
    invitation: str = Field(min_length=1)
    stop: str = Field(min_length=1)
    feedback_limits: str = Field(min_length=1)


class SupportReference(ContentModel):
    """Server-owned provenance of an actual execution, never a benefit claim."""

    identifier: str
    version: str
    kind: Literal["card", "exercise"]
    step: int = Field(ge=1)


class SourceRecord(ContentModel):
    id: str
    citation: str
    url: str = Field(pattern=r"^https?://")
    read_scope: str = Field(min_length=1)
    population: str = Field(min_length=1)
    supports: str = Field(min_length=1)
    limitations: str = Field(min_length=1)
    verification: Literal["checked", "unavailable", "pending"]
    checked_on: str


class ContentReview(ContentModel):
    item: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    source_check: Literal["passed", "failed", "pending"]
    automatic_review: Literal["passed", "failed", "pending"]
    reviewer: Literal["codex_automated"]
    reviewed_on: str
    rationale: str = Field(min_length=1)


class ItemAcceptance(ContentModel):
    item: str
    deterministic_cases: tuple[str, ...] = Field(min_length=1)
    live_scenarios: tuple[str, ...] = Field(min_length=1)
    covered_behaviors: tuple[
        Literal["applicable", "excluded", "permission_refusal", "exit", "feedback"], ...
    ]
    result: Literal["passed", "failed", "pending"]


class AcceptanceReceipt(ContentModel):
    package_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    check_version: str
    deterministic: Literal["passed", "failed", "pending"]
    live_replay: Literal["passed", "failed", "pending"]
    scenario_ids: tuple[str, ...] = Field(min_length=1)
    evidence_path: str = Field(min_length=1)
    items: tuple[ItemAcceptance, ...] = Field(min_length=1)


class ContentManifest(ContentModel):
    version: str
    scope: Literal["course_synthetic_adult_roleplay"]
    sources: tuple[SourceRecord, ...] = Field(min_length=1)
    reviews: tuple[ContentReview, ...] = ()
    acceptance: AcceptanceReceipt | None = None


class SelectionDecision(ContentModel):
    strategy_id: str
    version: str
    eligible: bool
    reasons: tuple[str, ...]
    score: int = 0


class StrategySelection(ContentModel):
    catalog_version: str
    selected_ids: tuple[str, ...]
    decisions: tuple[SelectionDecision, ...]
