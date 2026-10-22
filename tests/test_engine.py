import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gqde.engine import ValidationError, score_document


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.document = json.loads(
            (Path(__file__).resolve().parents[1] / "examples/candidates.json").read_text()
        )

    def test_synthetic_inputs_never_marked_eligible(self):
        result = score_document(self.document)
        self.assertEqual(result["candidate_count"], 2)
        self.assertEqual(result["results"][0]["id"], "fictional-B")
        statuses = {item["id"]: item["status"] for item in result["results"]}
        self.assertEqual(statuses["fictional-A"], "NEEDS_EVIDENCE")
        self.assertEqual(statuses["fictional-B"], "BLOCKED")

    def test_repeatability(self):
        self.assertEqual(score_document(self.document), score_document(self.document))

    def test_missing_input_fails_closed(self):
        del self.document["candidates"][0]["observations"]["fees"]
        with self.assertRaisesRegex(ValidationError, "missing evidence"):
            score_document(self.document)

    def test_no_eval_or_code_execution(self):
        self.document["dimensions"][0]["metrics"][0]["expression"] = "__import__('os').system('echo bad')"
        with self.assertRaisesRegex(ValidationError, "unsafe"):
            score_document(self.document)

    def test_division_by_zero_is_an_error(self):
        self.document["candidates"][0]["observations"]["sales_previous"]["value"] = 0
        with self.assertRaisesRegex(ValidationError, "division by zero"):
            score_document(self.document)

    def test_timezones_required(self):
        self.document["candidates"][0]["observations"]["sale_price"]["observed_at"] = "2026-10-22T09:00:00"
        with self.assertRaisesRegex(ValidationError, "timezone"):
            score_document(self.document)

    def test_observed_inputs_with_passed_gates_can_be_eligible(self):
        for candidate in self.document["candidates"]:
            for observation in candidate["observations"].values():
                observation["kind"] = "observed"
                observation["source"] = "manual:test-only"
        self.document["decision"]["min_score"] = 0
        result = score_document(self.document)
        self.assertEqual({r["id"]: r["status"] for r in result["results"]}["fictional-A"], "ELIGIBLE")
        self.assertEqual({r["id"]: r["status"] for r in result["results"]}["fictional-B"], "BLOCKED")

    def test_stale_observation_requires_review(self):
        for observation in self.document["candidates"][0]["observations"].values():
            observation["kind"] = "observed"
        self.document["candidates"][0]["observations"]["fees"]["observed_at"] = "2026-10-01T09:00:00+08:00"
        self.document["decision"]["min_score"] = 0
        result = score_document(self.document)
        self.assertEqual(next(r for r in result["results"] if r["id"] == "fictional-A")["status"], "NEEDS_EVIDENCE")

    def test_invalid_weight_rejected(self):
        self.document["dimensions"][0]["weight"] = 0
        with self.assertRaisesRegex(ValidationError, "weight"):
            score_document(self.document)

    def test_function_and_power_rejected(self):
        for expr in ["max(1, 2)", "2 ** 10000", "sale_price.__class__"]:
            with self.subTest(expr=expr):
                doc = copy.deepcopy(self.document)
                doc["dimensions"][0]["metrics"][0]["expression"] = expr
                with self.assertRaises(ValidationError):
                    score_document(doc)


if __name__ == "__main__":
    unittest.main()
