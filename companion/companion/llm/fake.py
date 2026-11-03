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
        roles: dict[str, list] | None = None,
    ) -> None:
        self.streams = deque(streams or [])
        self.risks = deque(risks or [])
        self.analyses = deque(analyses or [])
        self.calls: list[str] = []
        self.lock = threading.Lock()
        self.pressure = "academic"
        self.risk_release: threading.Event | None = None
        self.reasoner_release: threading.Event | None = None
        self.roles = {name: deque(values) for name, values in (roles or {}).items()}
        self.role_releases = {}
        self.role_started = {}
        self.requests = []
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
        from companion.cognition.models import (
            Consolidation,
            DeltaResult,
            PlanCandidate,
            ReviewBrief,
            ReviewResult,
            SituationAssessment,
        )

        role = {
            SituationAssessment: "analysis",
            ReviewBrief: "brief",
            PlanCandidate: "planner",
            ReviewResult: "critic",
            DeltaResult: "delta",
            Consolidation: "memory",
        }.get(schema)
        if role:
            payload = json.loads(messages[1]["content"])
            if schema is Consolidation and payload.get("kind") == "end_consolidation":
                role = "end"
            return self._role(role, payload, schema, deadline, params)
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

    def _role(self, role, payload, schema, deadline, params):
        import time

        from companion.cognition.base import EvidenceRef
        from companion.cognition.models import Usage

        with self.lock:
            self.calls.append(role)
            self.requests.append({"role": role, "payload": payload})
            queue = self.roles.get(role)
            value = queue.popleft() if queue else None
            self.role_started.setdefault(role, threading.Event()).set()
        release = self.role_releases.get(role, self.reasoner_release)
        if release and not release.wait(max(0, deadline - time.monotonic())):
            raise TimeoutError("Fake role deadline exceeded")
        if isinstance(value, Exception):
            raise value
        if callable(value):
            value = value(payload)
        if value is None:
            turns = [r for r in payload.get("history", []) if r["role"] == "user"]
            latest = turns[-1] if turns else None
            ref = (
                EvidenceRef(
                    kind="user_turn",
                    id=latest["id"],
                    claim="合成用户表达",
                    quote=latest["text"][:100],
                ).model_dump()
                if latest
                else None
            )
            if role == "analysis":
                value = {
                    "facts": [{"statement": latest["text"][:240], "evidence": [ref]}]
                    if ref
                    else [],
                    "expressed_need": "solve"
                    if any("怎么办" in t["text"] for t in turns)
                    else "listen",
                    "topic_summary": latest["text"][:240] if latest else "",
                    "pressure_types": [self.pressure],
                    "pathway_signals": ["rumination"],
                    "readiness": "medium",
                }
            elif role == "brief":
                value = {
                    "concerns": [{"statement": "尊重原话与明确许可", "evidence": [ref]}]
                    if ref
                    else []
                }
            elif role == "planner":
                wants_help = payload["analysis"]["expressed_need"] == "solve"
                boundary = any(m["kind"] == "interaction_boundary" for m in payload["memory"])
                action = (
                    payload["kind"] == "deliberation"
                    and wants_help
                    and not boundary
                    and bool(payload.get("cards"))
                )
                value = {
                    "objective": "invite_action" if action else "listen",
                    "understanding": "先理解当前感受，尊重边界。",
                    "evidence": [ref],
                    "response_guidance": ["承接当前感受，不重复被拒绝的建议。"],
                    "candidate_actions": [
                        {
                            "action_id": payload["cards"][0]["id"],
                            "kind": "card",
                            "evidence": [ref],
                            "requires_permission": True,
                            "when_met": True,
                            "exclusions_present": False,
                        }
                    ]
                    if action
                    else [],
                }
            elif role == "critic":
                value = {
                    "candidate_id": payload["candidate_id"],
                    "candidate_version": payload["candidate_version"],
                    "verdict": "approve",
                }
            elif role == "delta":
                r = payload["new_turns"][-1]
                value = {
                    "verdict": "compatible",
                    "reason": "合成兼容延续",
                    "evidence": [{"kind": "user_turn", "id": r["id"], "claim": "新增原话"}],
                }
            else:
                value = {
                    "summary": self.content["summary"] if role == "end" else None,
                    "memory_candidates": [],
                }
        result = schema.model_validate(value)
        if params.get("usage_callback"):
            params["usage_callback"](Usage(input_tokens=100, output_tokens=100, source="estimated"))
        return result
