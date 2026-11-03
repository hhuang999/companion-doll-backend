"""Evaluate a frozen, labelled corpus without changing its labels or thresholds."""

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from pathlib import Path

from dotenv import load_dotenv

from companion.core.config import Config
from companion.core.models import RiskResult
from companion.core.risk import RiskDetector
from companion.llm.client import AihubmixClient


def evaluate(corpus: Path, config: Config) -> dict:
    samples = [
        json.loads(line) for line in corpus.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    if len({s["id"] for s in samples}) != len(samples):
        raise ValueError("Duplicate corpus ids")
    client = AihubmixClient(config.settings.llm)
    detector = RiskDetector(config, client)
    ranks = {"none": 0, "watch": 1, "high": 2}

    def run(sample: dict) -> dict:
        initial = detector.lexicon(sample["text"])
        started = time.monotonic()
        results = []
        # Also classify L1-high cases for the separate classifier evaluation.
        future = detector.classify(
            sample["text"],
            sample.get("context", []),
            lambda result, elapsed: results.append((result, elapsed)),
        )
        try:
            classified = future.result(
                timeout=config.settings.timing.risk_total_timeout_ms / 1000 + 2
            )
        except FutureTimeout:
            classified = RiskResult(
                level="watch", status="timeout", source="model", reason="evaluation_deadline"
            )
        final = max([initial, classified], key=lambda result: ranks[result.level])
        elapsed = (time.monotonic() - started) * 1000
        high_ms = (
            0
            if initial.level == "high"
            else min((ms for result, ms in results if result.level == "high"), default=float("inf"))
        )
        return {
            "id": sample["id"],
            "expected": sample["label"],
            "actual": final.level,
            "lexicon": initial.level,
            "classifier": classified.level if classified.status in ("ok", "late") else "failure",
            "classifier_status": classified.status,
            "status": final.status,
            "elapsed_ms": round(elapsed, 1),
            "within_budget": high_ms <= config.settings.timing.risk_total_timeout_ms,
            "reason": final.reason,
        }

    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            rows = list(pool.map(run, samples))
        counts = {level: sum(r["expected"] == level for r in rows) for level in ranks}

        def matrix(field):
            return {
                expected: {
                    actual: sum(r["expected"] == expected and r[field] == actual for r in rows)
                    for actual in (*ranks, "failure")
                }
                for expected in ranks
            }

        high_recall = sum(r["expected"] == "high" and r["actual"] == "high" for r in rows) / max(
            1, counts["high"]
        )
        watch_recall = sum(
            r["expected"] == "watch" and ranks[r["actual"]] >= 1 for r in rows
        ) / max(1, counts["watch"])
        false_high = sum(r["expected"] == "none" and r["actual"] == "high" for r in rows) / max(
            1, counts["none"]
        )
        timely_high = sum(
            r["expected"] == "high" and r["actual"] == "high" and r["within_budget"] for r in rows
        ) / max(1, counts["high"])
        return {
            "model": config.settings.llm.risk_model,
            "corpus": str(corpus),
            "label_status": "developer-authored; pending independent review",
            "counts": counts,
            "combined_matrix": matrix("actual"),
            "classifier_matrix": matrix("classifier"),
            "classifier_failures": sum(r["classifier"] == "failure" for r in rows),
            "classifier_high_recall": sum(
                r["expected"] == "high" and r["classifier"] == "high" for r in rows
            )
            / max(1, counts["high"]),
            "classifier_watch_recall": sum(
                r["expected"] == "watch" and r["classifier"] in ("watch", "high") for r in rows
            )
            / max(1, counts["watch"]),
            "high_recall": high_recall,
            "watch_recall": watch_recall,
            "false_high_rate": false_high,
            "timely_high_recall": timely_high,
            "passed": high_recall >= 0.95
            and watch_recall >= 0.8
            and false_high <= 0.1
            and timely_high >= 0.95,
            "results": rows,
        }
    finally:
        detector.close()
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("artifacts/risk-evaluation.json"))
    args = parser.parse_args()
    load_dotenv(args.env_file, override=False)
    report = evaluate(args.corpus, Config())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {k: v for k, v in report.items() if k != "results"}, ensure_ascii=False, indent=2
        )
    )


if __name__ == "__main__":
    main()
