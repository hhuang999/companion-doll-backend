"""Bounded, opt-in model capability probe; never prints credentials."""

import argparse
import json
import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv


def probe(env_file: Path, output: Path, include_tts: bool = False) -> dict:
    load_dotenv(env_file, override=False)
    key = os.environ.get("AIHUBMIXKEY")
    if not key:
        raise ValueError("AIHUBMIXKEY is required")
    report = {"base_url": "https://aihubmix.com/v1", "checks": []}
    with httpx.Client(
        base_url=report["base_url"], headers={"Authorization": f"Bearer {key}"}, timeout=25
    ) as client:
        result = client.get("/models")
        result.raise_for_status()
        ids = [m["id"] for m in result.json()["data"]]
        report["candidate_models"] = [
            m
            for m in ids
            if any(s in m.lower() for s in ("qwen-flash", "qwen-plus", "tts", "cosy", "speech"))
        ]
        for model, kind in [
            ("qwen-flash", "stream"),
            ("qwen-flash", "json"),
            ("qwen-plus", "json"),
        ]:
            started = time.monotonic()
            check = {"model": model, "kind": kind}
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": 'Return exactly JSON: {"ok":true}'
                        if kind == "json"
                        else "请用一句简短中文打招呼。",
                    }
                ],
                "max_tokens": 80,
                "enable_thinking": False,
            }
            try:
                if kind == "stream":
                    payload["stream"] = True
                    parts = []
                    with client.stream("POST", "/chat/completions", json=payload) as response:
                        check["http_status"] = response.status_code
                        response.raise_for_status()
                        for line in response.iter_lines():
                            if not line.startswith("data: ") or line == "data: [DONE]":
                                continue
                            event = json.loads(line[6:])
                            for choice in event.get("choices", []):
                                text = choice.get("delta", {}).get("content")
                                if text:
                                    check.setdefault(
                                        "first_token_ms",
                                        round((time.monotonic() - started) * 1000, 1),
                                    )
                                    parts.append(text)
                    check["text"] = "".join(parts)
                    check["ok"] = bool(parts)
                else:
                    payload["response_format"] = {"type": "json_object"}
                    response = client.post("/chat/completions", json=payload)
                    check["http_status"] = response.status_code
                    response.raise_for_status()
                    content = response.json()["choices"][0]["message"]["content"]
                    check["parsed"] = json.loads(content)
                    check["degraded"] = response.headers.get("X-Structured-Output-Degraded")
                    check["ok"] = check["parsed"].get("ok") is True
            except (httpx.HTTPError, ValueError, KeyError) as error:
                check["ok"] = False
                check["error_type"] = type(error).__name__
            check["total_ms"] = round((time.monotonic() - started) * 1000, 1)
            report["checks"].append(check)
        if include_tts:
            started = time.monotonic()
            check = {"model": "gpt-4o-mini-tts", "kind": "tts"}
            try:
                response = client.post(
                    "/audio/speech",
                    json={
                        "model": check["model"],
                        "voice": "coral",
                        "input": "你好，我在这里。",
                        "response_format": "wav",
                    },
                )
                check["http_status"] = response.status_code
                response.raise_for_status()
                check["content_type"] = response.headers.get("content-type")
                check["bytes"] = len(response.content)
                check["ok"] = response.content.startswith(b"RIFF")
                if check["ok"]:
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.with_suffix(".wav").write_bytes(response.content)
            except httpx.HTTPError as error:
                check["ok"] = False
                check["error_type"] = type(error).__name__
            check["total_ms"] = round((time.monotonic() - started) * 1000, 1)
            report["checks"].append(check)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("artifacts/probe.json"))
    parser.add_argument("--tts", action="store_true")
    args = parser.parse_args()
    print(json.dumps(probe(args.env_file, args.output, args.tts), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
