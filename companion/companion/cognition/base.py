from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EvidenceRef(Contract):
    kind: Literal["user_turn", "memory", "interaction_event"]
    id: str | int
    claim: str = Field(max_length=240)
    quote: str | None = Field(default=None, max_length=300)
