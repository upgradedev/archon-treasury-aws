"""The J3 benchmark is code, so it is tested like code."""

import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_benchmark.py"
spec = importlib.util.spec_from_file_location("run_benchmark", SCRIPT)
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


class BenchmarkTest(unittest.TestCase):
    def test_engine_beats_naive_baseline_on_frozen_cases(self):
        result = bench.run_benchmark()
        self.assertEqual(result["cases"], 74)
        self.assertEqual(result["engine_correct"], result["cases"])
        self.assertLess(result["baseline_correct"], result["engine_correct"])
        self.assertIn("not a hosted LLM", result["baseline_kind"])

    def test_case_mix_is_frozen(self):
        self.assertEqual(len(bench.rule_cases()), 62)
        self.assertEqual(len(bench.invalidation_cases()), 12)


if __name__ == "__main__":
    unittest.main()
