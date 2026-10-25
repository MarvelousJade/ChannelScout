"""Derive auditable resume metrics from an existing benchmark; no database access."""

import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path


def positive(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Expected a positive finite number")
    if not math.isfinite(value) or value <= 0:
        raise ValueError("Expected a positive finite number")
    return value


def quality(condition):
    queries = condition["queries"]
    if not queries:
        raise ValueError("Quality evaluation must contain queries")
    names = [q["query"] for q in queries]
    if len(names) != len(set(names)):
        raise ValueError("Quality queries must be unique")
    scores = [q["precision_at_5"] for q in queries]
    if any(not math.isfinite(s) or not 0 <= s <= 1 for s in scores):
        raise ValueError("Precision must be finite and within [0, 1]")
    mean = statistics.mean(scores)
    if not math.isclose(mean, condition["mean_precision_at_5"], abs_tol=1e-12):
        raise ValueError("Stored quality mean does not match query scores")
    return names, mean


def summarize(report):
    baseline_names, baseline = quality(report["quality"]["0"])
    selected_names, selected = quality(report["quality"]["2"])
    if baseline_names != selected_names:
        raise ValueError("Quality conditions must evaluate the same ordered queries")
    latency = report["plans_and_latency"]
    samples = [positive(latency[c]["n"]) for c in ("indexed", "unindexed")]
    if samples[0] != samples[1] or any(int(n) != n for n in samples):
        raise ValueError("Latency conditions must have equal positive integer sample counts")
    comparison = {}
    for metric in ("p50_ms", "p95_ms"):
        before = positive(latency["unindexed"][metric])
        after = positive(latency["indexed"][metric])
        comparison[metric] = {
            "unindexed": before,
            "indexed": after,
            "reduction_percent": (before - after) / before * 100,
        }
    return {
        "evidence_type": "Previously recorded local synthetic benchmark; not a fresh DB run",
        "environment": report["environment"],
        "query_count": len(selected_names),
        "samples_per_latency_condition": samples[0],
        "quality": {
            "baseline_normalization": 0,
            "selected_normalization": 2,
            "baseline_mean_precision_at_5": baseline,
            "selected_mean_precision_at_5": selected,
            "gain_percentage_points": (selected - baseline) * 100,
            "zero_result_queries": [
                q["query"] for q in report["quality"]["2"]["queries"] if not q["top_ids"]
            ],
        },
        "latency": comparison,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="docs/benchmark-final.json")
    parser.add_argument("--output", default="docs/impact-metrics.json")
    args = parser.parse_args()
    raw = Path(args.input).read_bytes()
    summary = summarize(json.loads(raw))
    summary["source"] = {
        "path": Path(args.input).as_posix(),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    Path(args.output).write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
