"""Prepare the pinned local server configuration and missing SenseVoice weights."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import httpx
import yaml

MODEL_REVISION = "3847d57b6bdf2dd8875cb1508d2af43d80a16bf7"
MODEL_SHA256 = "833ca2dcfdf8ec91bd4f31cfac36d6124e0c459074d5e909aec9cabe6204a3ea"
MODEL_HASHES = {
    "model.pt": MODEL_SHA256,
    "am.mvn": "29b3c740a2c0cfc6b308126d31d7f265fa2be74f3bb095cd2f143ea970896ae5",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--download-model", action="store_true")
    args = parser.parse_args()
    root = args.project_root.resolve()
    server = root / "vendor/xiaozhi-esp32-server/main/xiaozhi-server"
    if not (server / "app.py").is_file():
        raise FileNotFoundError("Clone and patch the pinned upstream repository first")
    config_dir = root / "data/xiaozhi-config"
    if not config_dir.exists():
        shutil.copytree(root / "companion/companion/config", config_dir)
        settings_file = config_dir / "settings.yaml"
        settings = yaml.safe_load(settings_file.read_text(encoding="utf-8"))
        settings["storage"]["db_path"] = "data/xiaozhi.db"
        settings_file.write_text(yaml.safe_dump(settings, allow_unicode=True), encoding="utf-8")
    overrides = yaml.safe_load(
        Path(__file__).with_name("config.example.yaml").read_text(encoding="utf-8")
    )
    for section, provider in (("LLM", "CompanionLLM"), ("Memory", "CompanionMemory")):
        overrides[section][provider].update(
            project_root=root.as_posix(), config_dir=config_dir.as_posix()
        )
    overrides["prompt_template"] = (root / "xiaozhi_patch/companion-prompt.txt").as_posix()
    overrides["server"] = {
        "ip": "127.0.0.1",
        "port": 8000,
        "http_port": 8003,
        "websocket": "ws://127.0.0.1:8000/xiaozhi/v1/",
    }
    destination = server / "data/.config.yaml"
    destination.parent.mkdir(exist_ok=True)
    if destination.exists():
        print(f"Keeping existing configuration: {destination}")
    else:
        destination.write_text(
            yaml.safe_dump(overrides, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        print(f"Configuration written: {destination}")
    if args.download_model:
        directory = server / "models/SenseVoiceSmall"
        base = f"https://huggingface.co/FunAudioLLM/SenseVoiceSmall/resolve/{MODEL_REVISION}/"
        with httpx.Client(follow_redirects=True, timeout=60) as client:
            for name in ("am.mvn", "model.pt"):
                path = directory / name
                if path.is_file():
                    digest = hashlib.sha256()
                    with path.open("rb") as file:
                        for chunk in iter(lambda: file.read(1024 * 1024), b""):
                            digest.update(chunk)
                    if digest.hexdigest() != MODEL_HASHES[name]:
                        raise ValueError(f"Existing {name} checksum mismatch: {path}")
                    print(f"Verified existing model file: {name}")
                    continue
                temporary = path.with_suffix(path.suffix + ".part")
                digest = hashlib.sha256()
                size = 0
                print(f"Downloading {name} from pinned official model revision", flush=True)
                with client.stream("GET", base + name) as response:
                    response.raise_for_status()
                    with temporary.open("wb") as file:
                        for chunk in response.iter_bytes(1024 * 1024):
                            file.write(chunk)
                            digest.update(chunk)
                            size += len(chunk)
                if digest.hexdigest() != MODEL_HASHES[name]:
                    raise ValueError(f"SenseVoice {name} checksum mismatch")
                temporary.replace(path)
                print(f"Saved {name}: {size} bytes", flush=True)
        (root / "artifacts").mkdir(exist_ok=True)
        (root / "artifacts/sensevoice-download.json").write_text(
            json.dumps(
                {
                    "repository": "FunAudioLLM/SenseVoiceSmall",
                    "revision": MODEL_REVISION,
                    "model_sha256": MODEL_SHA256,
                },
                indent=2,
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
