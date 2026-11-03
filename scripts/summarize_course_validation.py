"""Create aggregate-only public evidence from local synthetic acceptance reports."""

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path


def distribution(values):
    values = sorted(v for v in values if isinstance(v, (int, float)))
    if not values:
        return {"n": 0}

    def percentile(p):
        position = (len(values) - 1) * p
        left = int(position)
        right = min(left + 1, len(values) - 1)
        return round(values[left] + (values[right] - values[left]) * (position - left), 1)

    return {
        "n": len(values),
        "p50": percentile(0.5),
        "p90": percentile(0.9),
        "max": round(values[-1], 1),
    }


def usage_summary(runs, turns):
    totals = Counter()
    sources = Counter()
    for value in [json.loads(run["usage"]) for run in runs] + [
        metrics[key]
        for metrics in turns
        for key in ("talker_usage", "risk_usage")
        if key in metrics
    ]:
        sources[value.get("source", "unknown")] += 1
        for key in ("input_tokens", "output_tokens"):
            totals[key] += value.get(key) or 0
    return {
        **totals,
        "records_by_source": dict(sources),
        "cost": "Provider bill not available; tokens are not a currency estimate.",
    }


def quality(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    runs = [r for case in data["scenarios"] for r in case["tables"]["agent_runs"]]
    jobs = [j for case in data["scenarios"] for j in case["tables"]["cognitive_jobs"]]
    turns = [json.loads(s["turn"]["latency"]) for c in data["scenarios"] for s in c["samples"]]
    durations = [
        (
            datetime.fromisoformat(j["finished_at"]) - datetime.fromisoformat(j["started_at"])
        ).total_seconds()
        * 1000
        for j in jobs
        if j["started_at"] and j["finished_at"]
    ]
    return {
        "run": path.parent.name,
        "suite_version": data["suite_version"],
        "suite_sha256": data["suite_sha256"],
        "package_digest": data["package_digest"],
        "models": data.get("models", {}),
        "fake": data["fake"],
        "scenarios": [
            {
                "id": c["id"],
                "checks": c["automatic_checks"],
                "recorded_turns": len(c["samples"]),
            }
            for c in data["scenarios"]
        ],
        "jobs": dict(Counter(j["status"] for j in jobs)),
        "roles": {
            role: {
                "status": dict(Counter(r["status"] for r in runs if r["role"] == role)),
                "duration_ms": distribution([r["duration_ms"] for r in runs if r["role"] == role]),
            }
            for role in sorted({r["role"] for r in runs})
        },
        "job_duration_ms": distribution(durations),
        "first_sentence_ms": distribution([t.get("first_sentence_ms") for t in turns]),
        "talker_fallbacks": sum(bool(t.get("fallback")) for t in turns),
        "risk_status": dict(Counter(t.get("risk_status", "not_recorded") for t in turns)),
        "usage": usage_summary(runs, turns),
    }


def voice(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    turns = [s.get("metrics", {}) for s in data["samples"]]
    runs, jobs = data["agent_runs"], data["jobs"]
    durations = [
        (
            datetime.fromisoformat(j["finished_at"]) - datetime.fromisoformat(j["started_at"])
        ).total_seconds()
        * 1000
        for j in jobs
        if j["started_at"] and j["finished_at"]
    ]
    return {
        "run": path.parent.name,
        "attempts": len(data["samples"]),
        "status": dict(Counter(s["status"] for s in data["samples"])),
        "dynamic": sum(bool(s.get("dynamic")) for s in data["samples"]),
        "fallbacks": sum(bool(t.get("fallback")) for t in turns),
        "summary_ms": data["summary"],
        "tts_duration_ms": distribution(
            [
                t["tts_complete_ms"] - t["tts_start_ms"]
                for t in turns
                if "tts_complete_ms" in t and "tts_start_ms" in t
            ]
        ),
        "encoding_to_ready_ms": distribution(
            [
                t["opus_first_packet_ready_ms"] - t["tts_complete_ms"]
                for t in turns
                if "opus_first_packet_ready_ms" in t and "tts_complete_ms" in t
            ]
        ),
        "jobs": dict(Counter(j["status"] for j in jobs)),
        "job_duration_ms": distribution(durations),
        "roles": dict(Counter(r["status"] for r in runs)),
        "usage": usage_summary(runs, turns),
        "end_tasks": data["end_tasks"],
        "load": "One sequential synthetic WebSocket client; ordinary background enabled; no simultaneous quality replay; dynamic TTS uncached.",
        "hardware": "No ESP32 playback ACK or speaker onset measured.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--voice", nargs="*", type=Path, default=[])
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            {
                "quality_runs": [quality(p) for p in args.reports],
                "voice_runs": [voice(p) for p in args.voice],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(args.reports)} aggregate reports to {args.output}")


if __name__ == "__main__":
    main()
