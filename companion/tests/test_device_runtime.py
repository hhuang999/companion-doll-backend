from unittest.mock import Mock

import pytest
from companion.adapters.xiaozhi import runtime


@pytest.mark.parametrize("failure", ["audio", "tts"])
def test_invalid_device_dependencies_do_not_start_the_core(tmp_path, config, monkeypatch, failure):
    options = {"project_root": str(tmp_path)}
    build = Mock()
    monkeypatch.setattr(runtime, "Config", lambda _: config)
    monkeypatch.setattr(runtime, "build_core", build)
    monkeypatch.setattr(runtime, "_instances", {})
    audio = Mock(side_effect=ValueError("invalid audio") if failure == "audio" else None)
    tts = Mock(side_effect=ValueError("missing TTS credentials") if failure == "tts" else None)
    monkeypatch.setattr(runtime, "validate_audio_manifest", audio)
    monkeypatch.setattr(runtime, "TTSClient", tts)
    with pytest.raises(ValueError):
        runtime.get_core(options)
    build.assert_not_called()
    assert not runtime._instances


def test_device_core_startup_failure_closes_the_tts_client(tmp_path, config, monkeypatch):
    monkeypatch.setattr(runtime, "_instances", {})
    monkeypatch.setattr(runtime, "Config", lambda _: config)
    monkeypatch.setattr(runtime, "validate_audio_manifest", Mock())
    tts = Mock()
    monkeypatch.setattr(runtime, "TTSClient", lambda _: tts)
    monkeypatch.setattr(runtime, "build_core", Mock(side_effect=RuntimeError("writer busy")))
    with pytest.raises(RuntimeError, match="writer busy"):
        runtime.get_core({"project_root": str(tmp_path)})
    tts.close.assert_called_once()
    assert not runtime._instances
