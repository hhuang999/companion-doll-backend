from pathlib import Path

import pytest
from companion.adapters.scenarios import replay
from companion.core.api import CompanionCore
from companion.llm.fake import FakeLLM


@pytest.mark.parametrize(
    "path", sorted((Path(__file__).parent / "scenarios").glob("*.yaml")), ids=lambda path: path.stem
)
def test_base_scenario(config, store, path):
    core = CompanionCore(config, store, FakeLLM())
    try:
        assert replay(core, path)["passed"]
    finally:
        core.close()
