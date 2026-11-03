"""Fail-closed course admission bound to the reviewed content bytes."""

import hashlib
import json
import wave
from pathlib import Path

import yaml


def item_digest(directory: Path, relative: str) -> str:
    path = (directory / relative).resolve()
    if not path.is_relative_to(directory.resolve()):
        raise ValueError("Content path escapes config directory")
    if path.suffix == ".yaml":
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        if relative.startswith("exercises/"):
            # Deployment paths and measured durations vary by machine; the spoken script
            # and pauses remain part of the reviewed digest. Audio is verified separately.
            for line in value.get("lines", []):
                line.pop("audio_path", None)
                line.pop("audio_duration_s", None)
        data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    else:
        data = path.read_text(encoding="utf-8").replace("\r\n", "\n").encode()
    return hashlib.sha256(data).hexdigest()


def package_digest(config) -> str:
    paths = content_paths(config)
    paths.extend(
        str(p.relative_to(config.directory)).replace("\\", "/")
        for p in sorted((config.directory / "prompts").glob("*.j2"))
    )
    paths.extend(["stages.yaml", "persona.yaml", "rules.yaml"])
    items = [(name, item_digest(config.directory, name)) for name in sorted(paths)]
    if config.content:
        items.append(
            (
                "source_registry",
                hashlib.sha256(
                    json.dumps(
                        [source.model_dump() for source in config.content.sources],
                        sort_keys=True,
                        ensure_ascii=False,
                    ).encode()
                ).hexdigest(),
            )
        )
    return hashlib.sha256(json.dumps(items, ensure_ascii=False).encode()).hexdigest()


def content_paths(config) -> list[str]:
    return (
        [f"cards/{identifier}.yaml" for identifier in config.cards]
        + [f"exercises/{identifier}.yaml" for identifier in config.exercises]
        + ["crisis.yaml"]
    )


def review_valid(config, relative: str) -> bool:
    if config.content is None:
        return False
    reviews = [r for r in config.content.reviews if r.item == relative]
    if len(reviews) != 1:
        return False
    review = reviews[0]
    sources = {s.id: s for s in config.content.sources}
    return (
        review.source_check == "passed"
        and review.automatic_review == "passed"
        and review.sha256 == item_digest(config.directory, relative)
        and all(i in sources and sources[i].verification == "checked" for i in review.evidence_ids)
    )


def validate_course_content(config) -> None:
    manifest = config.content
    if manifest is None:
        raise ValueError("Demo requires a course content manifest")
    if len({s.id for s in manifest.sources}) != len(manifest.sources):
        raise ValueError("Duplicate content source ID")
    if len({r.item for r in manifest.reviews}) != len(manifest.reviews):
        raise ValueError("Duplicate content review")
    if not config.cards:
        raise ValueError("Demo requires an enabled strategy catalog")
    for card in config.cards.values():
        if card.status != "enabled" or card.protocol is None:
            raise ValueError(f"Strategy is not enabled with a complete protocol: {card.id}")
        review = next((r for r in manifest.reviews if r.item == f"cards/{card.id}.yaml"), None)
        if review is None or set(review.evidence_ids) != set(card.protocol.evidence_ids):
            raise ValueError(f"Strategy/source review mismatch: {card.id}")
    for path in content_paths(config):
        if not review_valid(config, path):
            raise ValueError(f"Content check missing, failed or stale: {path}")
    if config.crisis.get("status") != "enabled":
        raise ValueError("Crisis course content is not enabled")
    for exercise in config.exercises.values():
        if exercise.status != "enabled":
            raise ValueError(f"Exercise is not enabled: {exercise.id}")
        for segment in exercise.lines:
            if not segment.audio_path or segment.audio_duration_s is None:
                raise ValueError(f"Exercise audio not measured: {exercise.id}")
            if not (config.directory / segment.audio_path).is_file():
                raise ValueError(f"Exercise audio missing: {segment.audio_path}")
            with wave.open(str(config.directory / segment.audio_path), "rb") as audio:
                measured = audio.getnframes() / audio.getframerate()
            if measured <= 0 or abs(measured - segment.audio_duration_s) > 0.02:
                raise ValueError(f"Exercise audio duration mismatch: {exercise.id}")
    from .audio import cache_key, validate_audio_manifest

    audio_manifest = validate_audio_manifest(config, config.directory / "audio_manifest.json")
    for exercise in config.exercises.values():
        if exercise.protocol is None:
            raise ValueError(f"Exercise protocol missing: {exercise.id}")
        review = next(r for r in manifest.reviews if r.item == f"exercises/{exercise.id}.yaml")
        if set(review.evidence_ids) != set(exercise.protocol.evidence_ids):
            raise ValueError(f"Exercise/source review mismatch: {exercise.id}")
        for segment in exercise.lines:
            key = cache_key(config.settings.tts.model, config.settings.tts.voice, segment.text)
            entry = audio_manifest["entries"][key]
            if (config.directory / segment.audio_path).resolve() != (
                config.directory / entry["path"]
            ).resolve():
                raise ValueError("Exercise audio does not match its spoken script")
    receipt = manifest.acceptance
    if receipt is None or receipt.package_digest != package_digest(config):
        raise ValueError("Course acceptance receipt missing or stale")
    if receipt.deterministic != "passed" or receipt.live_replay != "passed":
        raise ValueError("Course deterministic checks and live replay must pass")
    items = {entry.item: entry for entry in receipt.items}
    if len(items) != len(receipt.items) or set(items) != set(content_paths(config)):
        raise ValueError("Course acceptance must cover every enabled item exactly once")
    for item in items.values():
        if item.result != "passed" or set(item.covered_behaviors) != {
            "applicable",
            "excluded",
            "permission_refusal",
            "exit",
            "feedback",
        }:
            raise ValueError(f"Content behavior coverage incomplete: {item.item}")
