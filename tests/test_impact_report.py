"""Dependency-free checks: python -m unittest discover -s tests -p test_impact_report.py."""

import copy
import hashlib
import json
import unittest
from pathlib import Path

from scripts.impact_report import summarize


class ImpactReportTests(unittest.TestCase):
    def setUp(self):
        self.report = json.loads(Path("docs/benchmark-final.json").read_bytes())

    def test_recorded_evidence_and_committed_summary_agree(self):
        result = summarize(self.report)
        saved = json.loads(Path("docs/impact-metrics.json").read_bytes())
        source = saved.pop("source")
        self.assertEqual(result, saved)
        self.assertEqual(
            source["sha256"], hashlib.sha256(Path(source["path"]).read_bytes()).hexdigest()
        )
        self.assertEqual(result["query_count"], 30)
        self.assertEqual(result["samples_per_latency_condition"], 300)
        self.assertAlmostEqual(result["quality"]["gain_percentage_points"], 93.33333333333333)
        self.assertEqual(result["quality"]["zero_result_queries"], ["regex parser", "api page"])

    def test_percentage_reduction_uses_unindexed_denominator(self):
        self.report["plans_and_latency"]["unindexed"]["p95_ms"] = 10
        self.report["plans_and_latency"]["indexed"]["p95_ms"] = 8
        self.assertEqual(summarize(self.report)["latency"]["p95_ms"]["reduction_percent"], 20)
        self.report["plans_and_latency"]["indexed"]["p95_ms"] = 12
        self.assertEqual(summarize(self.report)["latency"]["p95_ms"]["reduction_percent"], -20)

    def test_invalid_latency_is_rejected(self):
        for value in (0, -1, float("nan"), float("inf"), True, "5"):
            with self.subTest(value=value):
                report = copy.deepcopy(self.report)
                report["plans_and_latency"]["unindexed"]["p95_ms"] = value
                with self.assertRaises(ValueError):
                    summarize(report)

    def test_inconsistent_quality_or_samples_are_rejected(self):
        changes = [
            ("quality", "2", "mean_precision_at_5", 0.5),
            ("quality", "2", "queries", []),
            ("plans_and_latency", "indexed", "n", 299),
            ("plans_and_latency", "indexed", "n", 300.5),
        ]
        for section, condition, field, value in changes:
            with self.subTest(field=field, value=value):
                report = copy.deepcopy(self.report)
                report[section][condition][field] = value
                with self.assertRaises(ValueError):
                    summarize(report)

    def test_different_query_sets_are_rejected(self):
        self.report["quality"]["2"]["queries"][0]["query"] = "different query"
        with self.assertRaises(ValueError):
            summarize(self.report)


if __name__ == "__main__":
    unittest.main()
