import re

from .config import Config
from .models import Stage


class OutputRail:
    def __init__(self, config: Config) -> None:
        self.rules = {
            name: tuple(re.compile(p) for p in patterns)
            for name, patterns in config.rules["output_rail"].items()
        }

    def check(
        self, sentence: str, stage: Stage, forbidden: tuple[str, ...] = ()
    ) -> tuple[str, ...]:
        violations = []
        for category, patterns in self.rules.items():
            if category == "advice" and stage == Stage.action:
                continue
            if any(pattern.search(sentence) for pattern in patterns):
                violations.append(f"rail_{category}")
        if any(phrase in sentence for phrase in forbidden):
            violations.append("rail_card")
        return tuple(violations)
