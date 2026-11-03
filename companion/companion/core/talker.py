"""Streaming tag parsing and sentence filtering; no session mutation."""

import re
import threading
import time
from collections.abc import Iterator

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from companion.llm.client import LLMClient

from .config import Config
from .models import TurnContext
from .output_rail import OutputRail


class Talker:
    def __init__(self, config: Config, llm: LLMClient) -> None:
        self.config = config
        self.llm = llm
        self.rail = OutputRail(config)
        self.env = Environment(
            loader=FileSystemLoader(config.directory / "prompts"),
            undefined=StrictUndefined,
            autoescape=False,
        )

    def parse_tag(self, line: str, context: TurnContext, violations: list[str]) -> str:
        match = re.fullmatch(
            r"<<state=([^;]+);card=([^;]+);emo=([^;]+);offer=([^>]+)>>", line.strip()
        )
        if not match:
            violations.append("missing_tag")
            return self.config.rules["emojis"]["default"]
        stage, card, emoji, offer = match.groups()
        if stage != context.stage.value:
            violations.append("tag_state_mismatch")
        if card != (context.card_id or "-"):
            violations.append("card_not_allowed")
        if offer != "-":
            # Invitations are issued by the deterministic template path.
            violations.append("offer_not_allowed")
        if emoji not in self.config.rules["emojis"]["allowed"]:
            violations.append("emoji_not_allowed")
            return self.config.rules["emojis"]["default"]
        return emoji

    def run(
        self,
        context: TurnContext,
        history: list[dict],
        cancel: threading.Event,
        metrics: dict,
        violations: list[str],
        step: int = 1,
        sentence_limit: int | None = None,
    ) -> Iterator[tuple[str, str]]:
        config = self.config
        sentence_limit = sentence_limit or config.settings.dialogue.max_sentences
        card = config.cards.get(context.card_id)
        prompt = self.env.get_template("talker.j2").render(
            persona=config.persona,
            rules=config.rules,
            context=context,
            stage=config.stages[context.stage.value],
            card=card,
            step=step,
            memory=context.snapshot.core_memory.model_dump_json()[:450],
            signals=context.signals.model_dump_json(),
        )
        messages = [{"role": "system", "content": prompt}]
        messages += [{"role": r["role"], "content": r["text"]} for r in history]
        if not history or history[-1].get("id") != context.turn_id:
            messages.append({"role": "user", "content": context.text})
        stream = self.llm.stream_chat(
            config.settings.llm.talker_model,
            messages,
            cancel,
            context.t0 + config.settings.timing.talker_total_timeout_s,
            first_token_timeout_s=config.settings.timing.talker_first_token_timeout_ms / 1000,
            temperature=0.7,
            max_tokens=160,
        )
        header = ""
        buffer = ""
        parsed = False
        discard_header = False
        emoji = config.rules["emojis"]["default"]
        count = 0
        questions = 0
        punctuation = set("。！？!?…；\n")
        try:
            for token in stream:
                if cancel.is_set():
                    return
                metrics.setdefault("first_token_ms", (time.monotonic() - context.t0) * 1000)
                if discard_header:
                    if "\n" not in token:
                        continue
                    _, token = token.split("\n", 1)
                    discard_header = False
                if not parsed:
                    header += token
                    if "\n" in header:
                        line, buffer = header.split("\n", 1)
                        emoji = self.parse_tag(line, context, violations)
                        if not line.startswith("<<"):
                            buffer = line + "\n" + buffer
                        parsed = True
                    elif len(header) > 256:
                        violations.append("missing_tag")
                        buffer = "" if header.startswith("<<") else header
                        discard_header = header.startswith("<<")
                        parsed = True
                    else:
                        continue
                else:
                    buffer += token
                while True:
                    boundary = next(
                        (i + 1 for i, char in enumerate(buffer) if char in punctuation and i >= 3),
                        None,
                    )
                    if boundary is None:
                        break
                    sentence, buffer = buffer[:boundary].strip(), buffer[boundary:]
                    if not sentence:
                        continue
                    metrics.setdefault("first_sentence_ms", (time.monotonic() - context.t0) * 1000)
                    rejected = self.rail.check(
                        sentence, context.stage, tuple(card.talker.never_say) if card else ()
                    )
                    question_count = sum(sentence.count(mark) for mark in ("?", "？"))
                    if questions + question_count > 1:
                        rejected += ("rail_questions",)
                    if rejected:
                        violations.extend(rejected)
                        continue
                    if count >= sentence_limit:
                        violations.append("too_many_sentences")
                        return
                    questions += question_count
                    count += 1
                    yield sentence, emoji
                    if count >= sentence_limit:
                        if buffer.strip():
                            violations.append("too_many_sentences")
                        return
            if not parsed:
                violations.append("missing_tag")
                buffer = "" if header.startswith("<<") else header
            if buffer.strip() and count < sentence_limit and not cancel.is_set():
                rejected = self.rail.check(
                    buffer.strip(), context.stage, tuple(card.talker.never_say) if card else ()
                )
                if questions + buffer.count("?") + buffer.count("？") > 1:
                    rejected += ("rail_questions",)
                if rejected:
                    violations.extend(rejected)
                else:
                    count += 1
                    metrics.setdefault("first_sentence_ms", (time.monotonic() - context.t0) * 1000)
                    yield buffer.strip(), emoji
            if count == 0 and not cancel.is_set():
                metrics["fallback"] = True
                yield config.stages[context.stage.value]["fallback"], emoji
        finally:
            close = getattr(stream, "close", None)
            if close:
                close()
