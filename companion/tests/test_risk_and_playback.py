import threading

import pytest
from companion.adapters.output import RecordingOutputPort
from companion.core.api import CompanionCore
from companion.core.models import RiskResult, TurnSignals
from companion.core.risk import RiskDetector
from companion.llm.fake import FakeLLM


@pytest.mark.parametrize("text", ["我不想自杀", "歌词里写着我想自杀", "笑死我了", "别人说他想跳楼"])
def test_lexicon_does_not_promote_negation_and_quotation(config, text):
    detector = RiskDetector(config, FakeLLM())
    try:
        assert detector.lexicon(text).level != "high"
    finally:
        detector.close()


def test_timeout_is_watch_not_safe(config, store):
    config.settings.timing.risk_total_timeout_ms = 50
    config.settings.timing.gate_timeout_ms = 1
    llm = FakeLLM()
    llm.risk_release = threading.Event()
    core = CompanionCore(config, store, llm)
    port = RecordingOutputPort(core.on_playback_event)
    core.bind_output("s", "u", port)
    try:
        identifier = core.on_input("s", "1", "hello", TurnSignals())
        for event in core.respond("s", identifier):
            core.dispatch(event)
        assert core.wait_idle(5)
        row = store.query("SELECT * FROM risk_events")[0]
        assert row["level"] == "watch"
        assert row["detection_status"] == "timeout"
    finally:
        llm.risk_release.set()
        core.close()


def test_late_high_after_disconnect_does_not_reach_reconnect(config, store):
    llm = FakeLLM(risks=[RiskResult(level="high")])
    llm.risk_release = threading.Event()
    core = CompanionCore(config, store, llm)
    old = RecordingOutputPort(core.on_playback_event)
    new = RecordingOutputPort(core.on_playback_event)
    core.bind_output("old", "u", old)
    try:
        core.on_input("old", "1", "ambiguous", TurnSignals())
        core.on_session_end("old", "disconnect")
        core.bind_output("new", "u", new)
        llm.risk_release.set()
        assert core.wait_idle(5)
        assert not new.events
        assert core.sessions["new"].state.mode == "normal"
        assert (
            store.query("SELECT level FROM risk_events WHERE session_id='old'")[0]["level"]
            == "high"
        )
    finally:
        llm.risk_release.set()
        core.close()


def test_output_port_deduplicates_and_rejects_old_generation():
    from companion.core.models import OutputEvent

    callbacks = []
    port = RecordingOutputPort(callbacks.append)
    event = OutputEvent(output_id="one", session_id="s", turn_id=1, generation=1, text="a")
    port.submit(event)
    port.submit(event)
    assert len(port.events) == 1
    port.cancel_before("s", 2)
    port.submit(event.model_copy(update={"output_id": "two"}))
    assert len(port.events) == 1
