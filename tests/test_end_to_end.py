import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import run_scenarios as scenarios


class EndToEndTests(unittest.TestCase):
    def run_case(self, operation):
        with tempfile.TemporaryDirectory() as directory:
            return operation(Path(directory))

    def test_mature_complete_candidate_and_no_op_repeat(self):
        result = self.run_case(scenarios.run_mature)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["verification"]["executed_checks"], 3)

    def test_component_independence_and_mechanism_erasure_counterexample(self):
        result = self.run_case(scenarios.run_extraction)
        self.assertEqual(result["status"], "passed")

    def test_blueprint_has_no_fabricated_runtime_claim(self):
        result = self.run_case(scenarios.run_research)
        self.assertEqual(result["status"], "passed")
        self.assertIsNone(result["verification"]["all_requested_checks_passed"])

    def test_public_evolution_preserves_source_and_detects_drift(self):
        result = self.run_case(scenarios.run_maintenance)
        self.assertEqual(result["status"], "passed")


if __name__ == "__main__":
    unittest.main()
