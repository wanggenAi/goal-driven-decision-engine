import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gqde.engine import ValidationError
from gqde.evaluate import evaluate_csv


class EvaluationTests(unittest.TestCase):
    def test_example_evaluation(self):
        report = evaluate_csv(Path(__file__).resolve().parents[1] / "examples/outcomes.csv")
        self.assertEqual(report["sample_count"], 3)
        self.assertAlmostEqual(report["mae"], 10.0)
        self.assertAlmostEqual(report["mean_bias"], 0.0)

    def test_empty_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "empty.csv"
            p.write_text("candidate_id,predicted,actual\n", encoding="utf-8")
            with self.assertRaises(ValidationError):
                evaluate_csv(p)


if __name__ == "__main__":
    unittest.main()
