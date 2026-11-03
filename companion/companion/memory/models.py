from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from companion.cognition.base import Contract, EvidenceRef, utcnow
from companion.content.models import SupportReference

MemoryKind = Literal[
    "fact_preference", "episodic_event", "interaction_boundary", "support_experience"
]
Scope = Literal["turn", "topic", "session", "until_time", "persistent"]


class MemoryCandidate(Contract):
    kind: MemoryKind
    key: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1, max_length=500)
    epistemic_status: Literal["stated", "observed", "hypothesized", "legacy_unverified"] = "stated"
    source_refs: tuple[EvidenceRef, ...] = Field(min_length=1, max_length=8)
    event_time: datetime | None = None
    scope: Scope = "session"
    scope_ref: str | None = None
    valid_from: datetime = Field(default_factory=utcnow)
    expires_at: datetime | None = None
    supersedes_id: str | None = None
    expected_version: int | None = Field(default=None, ge=1)
    sensitivity: Literal["ordinary", "sensitive"] = "ordinary"
    mention_policy: Literal["allowed", "only_when_raised", "avoid_proactive"] = "only_when_raised"
    importance: int = Field(default=5, ge=1, le=10)
    boundary_rule: (
        Literal["no_advice", "no_topic_probe", "no_memory_mention", "allow", "revoke"] | None
    ) = None
    target: str | None = Field(default=None, max_length=100)
    support: SupportReference | None = None
    feedback_valence: Literal["positive", "negative", "unknown"] = "unknown"

    @model_validator(mode="after")
    def validate_times(self):
        for value in (self.event_time, self.valid_from, self.expires_at):
            if value is not None and value.tzinfo is None:
                raise ValueError("Memory timestamps require a timezone")
        if self.scope == "until_time" and self.expires_at is None:
            raise ValueError("until_time requires expires_at")
        if self.expires_at and self.expires_at <= self.valid_from:
            raise ValueError("Memory expiry must follow valid_from")
        if self.kind == "interaction_boundary" and not self.boundary_rule:
            raise ValueError("Boundary requires a typed rule")
        return self


class MemoryItem(MemoryCandidate):
    schema_version: Literal[2] = 2
    memory_id: str
    user_key: str
    recorded_at: datetime = Field(default_factory=utcnow)
    status: Literal["active", "superseded", "invalidated", "expired"] = "active"
    version: int = Field(default=1, ge=1)
    source_cursor: int = Field(ge=0)


class MemoryBundle(Contract):
    boundaries: tuple[MemoryItem, ...] = ()
    items: tuple[MemoryItem, ...] = ()
    memory_revision: int = 0
    boundary_revision: int = 0
    estimated_tokens: int = 0
