"""Fixed audio provenance shared by preparation, admission and device startup."""

import hashlib
import json
import wave
from pathlib import Path


def cache_key(model, voice, text):
    return hashlib.sha256(f"{model}\n{voice}\n{text}".encode()).hexdigest()


def fixed_texts(config):
    texts = {line.text for script in config.exercises.values() for line in script.lines}
    texts.update(config.persona[key] for key in ("onboarding", "greeting", "rest", "idle_end"))
    crisis = config.crisis
    texts.update([crisis["opening"], crisis["resources"], crisis["closing"], *crisis["responses"]])
    texts.update(text + crisis["resources"] for text in crisis["responses"])
    return sorted(texts)


def validate_audio_manifest(config, path):
    path = Path(path)
    if not path.is_file():
        raise ValueError(
            "Fixed audio manifest missing; run companion.tools.prepare_audio --bind-config"
        )
    manifest = json.loads(path.read_text(encoding="utf-8"))
    settings = config.settings.tts
    if manifest.get("schema_version") != 1 or (manifest.get("model"), manifest.get("voice")) != (
        settings.model,
        settings.voice,
    ):
        raise ValueError("Fixed audio manifest model/voice/version mismatch")
    entries = manifest.get("entries", {})
    for text in fixed_texts(config):
        key = cache_key(settings.model, settings.voice, text)
        entry = entries.get(key)
        if not entry or entry.get("text_sha256") != hashlib.sha256(text.encode()).hexdigest():
            raise ValueError("Fixed audio script not bound to cache")
        audio_path = (path.parent / entry["path"]).resolve()
        if (
            not audio_path.is_file()
            or hashlib.sha256(audio_path.read_bytes()).hexdigest() != entry["sha256"]
        ):
            raise ValueError("Fixed audio missing or changed")
        with wave.open(str(audio_path), "rb") as audio:
            duration = audio.getnframes() / audio.getframerate()
        if duration <= 0 or abs(duration - entry["duration_s"]) > 0.02:
            raise ValueError("Fixed audio duration mismatch")
    for script in config.exercises.values():
        if manifest.get("exercise_pauses", {}).get(script.id) != [
            line.pause_s for line in script.lines
        ]:
            raise ValueError("Fixed audio pause schedule changed")
        duration = sum(
            entries[cache_key(settings.model, settings.voice, line.text)]["duration_s"]
            + line.pause_s
            for line in script.lines
        )
        if duration > config.settings.timing.exercise_max_s:
            raise ValueError(f"Exercise exceeds configured duration: {script.id}")
    return manifest
