"""Explicit paid API checks: pytest -m online. Offline is the default."""

import json
import os
import time
from pathlib import Path

import pytest
from companion.adapters.cli import build_core
from companion.adapters.output import RecordingOutputPort
from companion.core.models import TurnSignals
from companion.llm.tts import TTSClient
from companion.tools.risk_eval import evaluate
from dotenv import load_dotenv

pytestmark = pytest.mark.online
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def credentials():
    load_dotenv(ROOT / ".env", override=False)
    if not os.environ.get("AIHUBMIXKEY"):
        pytest.skip("AIHUBMIXKEY is not configured")


def test_live_conversation_and_summary(config, tmp_path):
    core = build_core(config, tmp_path / "online.db")
    port = RecordingOutputPort(core.on_playback_event)
    core.bind_output("online", "synthetic-online", port)
    try:
        for index, text in enumerate(
            ["今天数学考试没考好，我很失落", "我一直在想试卷上的错误，怎么办"]
        ):
            turn = core.on_input("online", str(index), text, TurnSignals())
            for event in core.respond("online", turn):
                core.dispatch(event)
            # v2 may serialize a repair strategy and a separate memory job.
            # This waits for the queue; each job retains its 20 s hard deadline.
            assert core.wait_idle(50)
        assert core.sessions["online"].state.pending_offer
        assert all("<<state" not in event.text for event in port.events)
        assert not core.store.query("SELECT id FROM turns WHERE output_status='error'")
        core.on_session_end("online", "online_test")
        assert core.wait_idle(50)
        assert core.store.query("SELECT status FROM end_tasks")[0]["status"] == "done"
        assert core.store.query("SELECT summary FROM sessions")[0]["summary"]
    finally:
        core.close()
        core.store.close()


def test_live_tts_returns_playable_wav(config):
    client = TTSClient(config)
    try:
        started = time.monotonic()
        data = client.synthesize("我在这里，慢慢说。")
        assert 0 < client.duration(data) < 15
        report = {
            "model": config.settings.tts.model,
            "elapsed_ms": (time.monotonic() - started) * 1000,
            "audio_seconds": client.duration(data),
        }
        (ROOT / "artifacts").mkdir(exist_ok=True)
        (ROOT / "artifacts/tts-online.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
    finally:
        client.close()


def test_live_risk_corpus(config):
    report = evaluate(Path(__file__).with_name("risk_set.jsonl"), config)
    (ROOT / "artifacts").mkdir(exist_ok=True)
    (ROOT / "artifacts/risk-pytest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    assert report["passed"], (
        "See artifacts/risk-pytest.json for classification and deadline failures"
    )
