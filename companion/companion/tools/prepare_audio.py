import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv

from companion.core.config import Config
from companion.llm.tts import TTSClient


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--config-dir", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/fixed_audio"))
    args = parser.parse_args()
    load_dotenv(args.env_file, override=False)
    config = Config(args.config_dir)
    client = TTSClient(config)
    texts = {line.text for script in config.exercises.values() for line in script.lines}
    texts.update(config.persona[key] for key in ("onboarding", "greeting", "rest", "idle_end"))
    crisis = config.crisis
    texts.update([crisis["opening"], crisis["resources"], crisis["closing"], *crisis["responses"]])
    # Composite crisis responses are fixed too; preload all possible rotations.
    texts.update(text + crisis["resources"] for text in crisis["responses"])
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
            "mode": config.settings.runtime.mode,
            "model": config.settings.tts.model,
            "voice": config.settings.tts.voice,
            "exercise_duration_s": plans,
            "within_90s": all(d <= 90 for d in plans.values()),
            "audio_count": len(durations),
        }
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "manifest.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        client.close()


if __name__ == "__main__":
    main()
