"""Configuration is validated once at startup, including referenced content."""

import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from companion.content.models import ContentManifest, ExerciseProtocol, StrategyProtocol

from .models import PlaybackSegment, Stage


class SettingsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RuntimeSettings(SettingsModel):
    mode: Literal["development", "demo"] = "development"
    timezone: str = "Asia/Shanghai"


class LLMSettings(SettingsModel):
    base_url: str = "https://aihubmix.com/v1"
    api_key_env: str = "AIHUBMIXKEY"
    talker_model: str = "qwen-flash"
    risk_model: str = "qwen-flash"
    reasoner_model: str = "qwen-plus"
    enable_thinking: bool = False


class Timing(SettingsModel):
    gate_timeout_ms: int = Field(default=600, ge=0)
    risk_total_timeout_ms: int = Field(default=2500, gt=0)
    talker_first_token_timeout_ms: int = Field(default=2500, gt=0)
    talker_total_timeout_s: float = Field(default=10, gt=0)
    reasoner_timeout_s: float = Field(default=20, gt=0)
    rest_reminder_s: float = Field(default=7200, gt=0)
    exercise_max_s: float = Field(default=90, gt=0, le=90)
    shutdown_grace_s: float = Field(default=25, gt=0)


class DialogueSettings(SettingsModel):
    history_turns: int = Field(default=10, gt=0)
    reasoner_context_turns: int = Field(default=12, gt=0)
    reasoner_every_n_turns: int = Field(default=4, gt=0)
    max_sentences: int = Field(default=3, gt=0, le=3)
    max_action_turns: int = Field(default=4, gt=0, le=4)
    offer_valid_turns: int = Field(default=2, gt=0)
    accepted_wait_turns: int = Field(default=2, gt=0)
    accepted_wait_s: float = Field(default=30, gt=0)


class PoolSettings(SettingsModel):
    risk_workers: int = Field(default=4, gt=0)
    reasoner_workers: int = Field(default=2, gt=0)


class StorageSettings(SettingsModel):
    db_path: str = "data/companion.db"
    busy_timeout_ms: int = Field(default=5000, gt=0)


class TTSSettings(SettingsModel):
    model: str = "gpt-4o-mini-tts"
    voice: str = "coral"
    response_format: Literal["wav"] = "wav"


class JobBudgetSettings(SettingsModel):
    max_calls: int = Field(gt=0)
    output_tokens: int = Field(gt=0)
    total_tokens: int = Field(gt=0)


class CognitionSettings(SettingsModel):
    model_workers: int = Field(default=2, ge=1, le=8)
    max_pending: int = Field(default=256, ge=1)
    queue_timeout_s: float = Field(default=30, gt=0)
    plan_ttl_s: float = Field(default=120, gt=0)
    plan_turn_delta: int = Field(default=4, ge=1)
    context_tokens: int = Field(default=1200, ge=300)
    analysis_model: str = "qwen-plus"
    brief_model: str = "qwen-flash"
    planner_model: str = "qwen-plus"
    critic_model: str = "qwen-flash"
    delta_model: str = "qwen-flash"
    memory_model: str = "gpt-4.1-mini"
    end_model: str = "gpt-4.1-mini"
    routine: JobBudgetSettings = Field(
        default_factory=lambda: JobBudgetSettings(
            max_calls=4, output_tokens=2400, total_tokens=16000
        )
    )
    deliberation: JobBudgetSettings = Field(
        default_factory=lambda: JobBudgetSettings(
            max_calls=8, output_tokens=6000, total_tokens=32000
        )
    )
    memory: JobBudgetSettings = Field(
        default_factory=lambda: JobBudgetSettings(
            max_calls=2, output_tokens=1800, total_tokens=16000
        )
    )
    end_consolidation: JobBudgetSettings = Field(
        default_factory=lambda: JobBudgetSettings(
            max_calls=2, output_tokens=2400, total_tokens=16000
        )
    )


class Settings(SettingsModel):
    runtime: RuntimeSettings = Field(default_factory=RuntimeSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    timing: Timing = Field(default_factory=Timing)
    dialogue: DialogueSettings = Field(default_factory=DialogueSettings)
    pools: PoolSettings = Field(default_factory=PoolSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    tts: TTSSettings = Field(default_factory=TTSSettings)
    cognition: CognitionSettings = Field(default_factory=CognitionSettings)
    alert_webhook: str | None = None


class Targets(SettingsModel):
    pressure_types: list[str] = Field(default_factory=list)
    pathways: list[str] = Field(default_factory=list)


class CardReasoner(SettingsModel):
    when_any: list[str]
    not_when: list[str]
    success: str
    exit: str


class CardTalker(SettingsModel):
    steps: list[str] = Field(min_length=1)
    examples: list[str]
    never_say: list[str]


class Card(SettingsModel):
    id: str = Field(pattern=r"^(S(0[3-9]|1[0-9])|[a-z][a-z0-9_]{2,47})$")
    name: str
    status: Literal["fixture", "draft", "approved", "enabled"]
    requires_permission: Literal[True] = True
    targets: Targets
    constraints: dict[str, list[str]]
    reasoner: CardReasoner
    talker: CardTalker
    limits: dict[str, int]
    emo: str
    source: dict[str, str]
    protocol: StrategyProtocol | None = None


class Exercise(SettingsModel):
    id: str
    name: str
    status: Literal["draft", "approved", "enabled"]
    emo: str
    lines: list[PlaybackSegment] = Field(min_length=1)
    protocol: ExerciseProtocol | None = None


class Config:
    def __init__(self, directory: Path | None = None, *, mode: str | None = None) -> None:
        self.directory = (directory or Path(__file__).parents[1] / "config").resolve()
        self.settings = Settings.model_validate(self.read("settings.yaml"))
        if mode:
            self.settings.runtime = RuntimeSettings(mode=mode)
        self.persona = self.read("persona.yaml")
        self.rules = self.read("rules.yaml")
        self.stages = self.read("stages.yaml")
        self.crisis = self.read("crisis.yaml")
        self.lexicon = self.read("risk_lexicon.yaml")
        self.content = (
            ContentManifest.model_validate(self.read("content_manifest.yaml"))
            if (self.directory / "content_manifest.yaml").is_file()
            else None
        )
        if self.crisis.get("status") == "enabled" and not self.content_reviewed("crisis.yaml"):
            raise ValueError("Enabled crisis content has incomplete/stale review")
        self.cards = {}
        for path in sorted((self.directory / "cards").glob("*.yaml")):
            card = Card.model_validate(self.read(str(path.relative_to(self.directory))))
            if card.id in self.cards or path.stem != card.id:
                raise ValueError(f"Duplicate or mismatched card: {path.name}")
            if card.limits.get("per_session", 0) < 1:
                raise ValueError(f"Invalid card limit: {card.id}")
            self.cards[card.id] = card
            if card.status == "enabled" and (
                card.protocol is None or not self.content_reviewed(f"cards/{card.id}.yaml")
            ):
                raise ValueError(f"Enabled strategy has incomplete/stale content review: {card.id}")
        self.exercises = {}
        for path in sorted((self.directory / "exercises").glob("*.yaml")):
            exercise = Exercise.model_validate(self.read(str(path.relative_to(self.directory))))
            if exercise.id in self.exercises:
                raise ValueError(f"Duplicate exercise: {exercise.id}")
            total = sum(s.pause_s + (s.audio_duration_s or 0) for s in exercise.lines)
            if total > self.settings.timing.exercise_max_s:
                raise ValueError(f"Exercise exceeds time limit: {exercise.id}")
            self.exercises[exercise.id] = exercise
            if exercise.status == "enabled" and (
                exercise.protocol is None
                or not self.content_reviewed(f"exercises/{exercise.id}.yaml")
            ):
                raise ValueError(
                    f"Enabled exercise has incomplete/stale content review: {exercise.id}"
                )
        for stage in Stage:
            if not self.stages.get(stage.value, {}).get("fallback"):
                raise ValueError(f"Missing stage: {stage.value}")
        for group in (self.rules["transitions"], self.rules["output_rail"]):
            for patterns in group.values():
                for pattern in patterns:
                    re.compile(pattern)
        for level in ("high", "watch"):
            for item in self.lexicon[level]:
                re.compile(item["pattern"])
        for key in ("opening", "responses", "resources", "closing", "version"):
            if not self.crisis.get(key):
                raise ValueError(f"Missing crisis field: {key}")
        from .output_rail import OutputRail

        rail = OutputRail(self)
        for stage in Stage:
            if rail.check(self.stages[stage.value]["fallback"], stage):
                raise ValueError(f"Fallback violates output rules: {stage.value}")
        if self.settings.runtime.mode == "demo":
            self.validate_demo()

    def read(self, name: str) -> dict:
        value = yaml.safe_load((self.directory / name).read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise TypeError(f"Expected mapping: {name}")
        return value

    def validate_demo(self) -> None:
        from companion.content.admission import validate_course_content

        validate_course_content(self)

    def content_reviewed(self, relative: str) -> bool:
        from companion.content.admission import review_valid

        return review_valid(self, relative)
