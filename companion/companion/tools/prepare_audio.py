import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml
from dotenv import load_dotenv

from companion.content.audio import fixed_texts, validate_audio_manifest
from companion.core.config import Config
from companion.llm.tts import TTSClient


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--config-dir", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/fixed_audio"))
    parser.add_argument(
        "--bind-config",
        action="store_true",
        help="Bind measured resources to an explicit deployment config copy",
    )
    args = parser.parse_args()
    load_dotenv(args.env_file, override=False)
    if args.bind_config and args.config_dir is None:
        parser.error("--bind-config requires --config-dir (use a deployment copy)")
    config = Config(args.config_dir, mode="development")
    client = TTSClient(config)
    texts = fixed_texts(config)
    durations = {}
    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            for text, (_, duration) in zip(
                sorted(texts),
                pool.map(lambda text: client.fixed_audio(text, args.output), sorted(texts)),
            ):
                durations[text] = duration
        plans = {
            script.id: sum(durations[line.text] + line.pause_s for line in script.lines)
            for script in config.exercises.values()
        }
        report = {
            "schema_version": 1,
            "mode": config.settings.runtime.mode,
            "model": config.settings.tts.model,
            "voice": config.settings.tts.voice,
            "exercise_duration_s": plans,
            "within_90s": all(d <= 90 for d in plans.values()),
            "audio_count": len(durations),
            "exercise_pauses": {
                script.id: [line.pause_s for line in script.lines]
                for script in config.exercises.values()
            },
            "entries": {
                client.cache_key(text): {
                    "path": str((args.output / f"{client.cache_key(text)}.wav").resolve()),
                    "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                    "sha256": hashlib.sha256(
                        (args.output / f"{client.cache_key(text)}.wav").read_bytes()
                    ).hexdigest(),
                    "duration_s": duration,
                }
                for text, duration in durations.items()
            },
        }
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "manifest.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        validate_audio_manifest(config, args.output / "manifest.json")
        if args.bind_config:
            for script in config.exercises.values():
                target = config.directory / "exercises" / f"{script.id}.yaml"
                value = yaml.safe_load(target.read_text(encoding="utf-8"))
                for line in value["lines"]:
                    entry = report["entries"][client.cache_key(line["text"])]
                    line.update(audio_path=entry["path"], audio_duration_s=entry["duration_s"])
                target.write_text(
                    yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8"
                )
            (config.directory / "audio_manifest.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            Config(config.directory, mode="development")
        print(
            json.dumps(
                {key: value for key, value in report.items() if key != "entries"},
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        client.close()


if __name__ == "__main__":
    main()
