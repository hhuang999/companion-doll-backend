"""Deterministic test double. Its assessments are fixtures, not model evaluation."""

import json
import re
import threading
from collections import deque
from collections.abc import Iterator
from pathlib import Path

import yaml
from pydantic import BaseModel

from companion.core.models import (
    Assessment,
    CardEvidence,
    CardSelection,
    ReasonerOutput,
    RiskResult,
    SeekerState,
    StageProposal,
    TypedConfidence,
)


class FakeLLM:
    def __init__(
        self,
        streams: list[str | Exception] | None = None,
        risks: list[RiskResult | Exception] | None = None,
        analyses: list[ReasonerOutput | Exception] | None = None,
    ) -> None:
        self.streams = deque(streams or [])
        self.risks = deque(risks or [])
        self.analyses = deque(analyses or [])
        self.calls: list[str] = []
        self.lock = threading.Lock()
        self.pressure = "academic"
        self.risk_release: threading.Event | None = None
        self.reasoner_release: threading.Event | None = None
        self.content = yaml.safe_load(
            (Path(__file__).parents[1] / "config/fake.yaml").read_text(encoding="utf-8")
        )

    def stream_chat(
        self,
        model: str,
        messages: list[dict],
        cancel: threading.Event,
        deadline: float,
        **params: object,
    ) -> Iterator[str]:
        with self.lock:
            self.calls.append("talker")
            value = self.streams.popleft() if self.streams else None
        if isinstance(value, Exception):
            raise value
        if value is None:
            label = re.search(r"<<state=([^;]+);card=([^;]+);", messages[0]["content"])
            stage, card = label.groups() if label else ("explore", "-")
            value = (
                f"<<state={stage};card={card};emo=😶;offer=->>\n{self.content['replies'][stage]}"
            )
        for index in range(0, len(value), 3):
            if cancel.is_set():
                return
            yield value[index : index + 3]

    def complete_json(
        self,
        model: str,
        messages: list[dict],
        schema: type[BaseModel],
        deadline: float,
        **params: object,
    ) -> BaseModel:
        is_risk = schema is RiskResult
        with self.lock:
            self.calls.append("risk" if is_risk else "reasoner")
            queue = self.risks if is_risk else self.analyses
            value = queue.popleft() if queue else None
        release = self.risk_release if is_risk else self.reasoner_release
        if release is not None:
            import time

            if not release.wait(max(0, deadline - time.monotonic())):
                raise TimeoutError("Fake model deadline exceeded")
        if isinstance(value, Exception):
            raise value
        if value is not None:
            return schema.model_validate(value)
        if is_risk:
            return RiskResult(source="model")
        data = json.loads(messages[-1]["content"])
        turns = [item["id"] for item in data["history"] if item["role"] == "user"]
        stage = data["state"]["stage"]
        proposal = {"explore": "comfort", "comfort": "permission", "action": "closing"}.get(stage)
        if data["ending"]:
            return ReasonerOutput(session_summary=self.content["summary"])
        return ReasonerOutput(
            assessment=Assessment(
                pressure_types=(TypedConfidence(type=self.pressure, confidence=0.7),),
                pathway_signals=("rumination",),
                seeker_state=SeekerState(readiness="medium"),
            ),
            stage_proposal=StageProposal(
                to=proposal, reason="fixture", source_turn_ids=tuple(turns[-1:])
            )
            if proposal and turns
            else None,
            cards=CardSelection(
                allowed=("S16",),
                preferred="S16",
                evidence=(
                    CardEvidence(
                        card_id="S16",
                        when_met=True,
                        exclusions_present=False,
                        source_turn_ids=tuple(turns[-1:]),
                    ),
                ),
            )
            if turns
            else CardSelection(),
        )
