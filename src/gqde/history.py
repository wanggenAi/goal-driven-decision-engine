"""Portable decision snapshots and out-of-time outcome evaluation, no training."""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path

from .engine import ValidationError, _number, _timestamp, score_document
from .model import ENGINE_VERSION, obj, observation, sequence, text, window


def digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def snapshot(document: dict, predictions: list | None = None) -> dict:
    report = score_document(document)
    if report["schema_version"] != "2.0":
        raise ValidationError("snapshots require schema 2.0")
    predictions = copy.deepcopy(predictions) if predictions is not None else []
    if not isinstance(predictions, list):
        raise ValidationError("predictions must be a list")
    ids, seen = {r["id"] for r in report["results"]}, set()
    for pred in predictions:
        obj(pred, "candidate_id value unit method baseline_value baseline_basis", label="prediction")
        cid = text(pred["candidate_id"], "prediction.candidate_id")
        if cid not in ids or cid in seen:
            raise ValidationError("unknown or duplicate prediction candidate")
        seen.add(cid)
        if pred["unit"] != document["goal"]["outcome_unit"]:
            raise ValidationError("prediction unit mismatch")
        for key in ("value", "baseline_value"):
            _number(pred[key], f"prediction.{key}")
        text(pred["method"], "prediction method")
        text(pred["baseline_basis"], "baseline_basis")
    payload = {"snapshot_version": "1.0", "engine_version": ENGINE_VERSION,
               "document": copy.deepcopy(document), "report": report, "predictions": predictions}
    return {**payload, "snapshot_id": digest(payload)}


def save_snapshot(value: dict, path: str | Path) -> None:
    # Exclusive creation avoids accidentally rewriting an earlier decision.
    verify_snapshot(value)
    with Path(path).open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def verify_snapshot(value: dict) -> None:
    obj(value, "snapshot_version engine_version document report predictions snapshot_id", label="snapshot")
    if value["snapshot_version"] != "1.0":
        raise ValidationError("unsupported snapshot_version")
    payload = {k: v for k, v in value.items() if k != "snapshot_id"}
    if digest(payload) != value["snapshot_id"]:
        raise ValidationError("snapshot digest mismatch")
    # Replay with the same implementation; future engines must retain old replay support.
    if value["engine_version"] != ENGINE_VERSION:
        raise ValidationError("snapshot engine version unsupported; use its recorded engine release")
    replay = snapshot(value["document"], value["predictions"])
    if replay != value:
        raise ValidationError("snapshot replay mismatch")


def spearman(x: list[float], y: list[float]) -> float | None:
    """Pearson correlation of average ranks, including ties; None for constants."""
    if not x or len(x) != len(y):
        raise ValidationError("rank correlation needs equal, nonempty samples")
    x = [_number(v, "rank input") for v in x]
    y = [_number(v, "rank input") for v in y]
    def ranks(values):
        return [1 + sum(v < value for v in values) + (sum(v == value for v in values) - 1) / 2
                for value in values]
    a, b = ranks(x), ranks(y)
    ma, mb = math.fsum(a) / len(a), math.fsum(b) / len(b)
    da, db = [v - ma for v in a], [v - mb for v in b]
    denominator = math.sqrt(math.fsum(v * v for v in da) * math.fsum(v * v for v in db))
    return math.fsum(u * v for u, v in zip(da, db)) / denominator if denominator else None


def forecast_errors(predicted: list[float], actual: list[float]) -> dict:
    if not predicted or len(predicted) != len(actual):
        raise ValidationError("forecast errors need equal, nonempty samples")
    predicted = [_number(v, "prediction") for v in predicted]
    actual = [_number(v, "actual") for v in actual]
    errors = [_number(p - a, "prediction error") for p, a in zip(predicted, actual)]
    scale = max(abs(e) for e in errors)
    n = len(errors)
    return {"sample_count": n, "mae": _number(math.fsum(abs(e) / n for e in errors), "MAE"),
            "rmse": _number(scale * math.sqrt(math.fsum((e / scale) ** 2 / n for e in errors)), "RMSE") if scale else 0,
            "mean_bias": _number(math.fsum(e / n for e in errors), "bias")}


def evaluate_history(saved: dict, outcomes: dict) -> dict:
    verify_snapshot(saved)
    doc, report = saved["document"], saved["report"]
    obj(outcomes, "schema_version snapshot_id as_of success_measure outcomes", label="outcomes")
    if outcomes["schema_version"] != "1.0" or outcomes["snapshot_id"] != saved["snapshot_id"]:
        raise ValidationError("outcomes must reference this snapshot")
    goal = doc["goal"]
    if outcomes["success_measure"] != goal["success_measure"]:
        raise ValidationError("outcome success_measure mismatch")
    as_of = _timestamp(outcomes["as_of"], "outcomes.as_of")
    _, end = window(goal["evaluation_window"], "evaluation_window")
    if as_of < end:
        raise ValidationError("outcome evaluation precedes horizon end")
    all_rows = {r["id"]: r for r in report["results"]}
    actual, kinds, verified = {}, set(), []
    for row in sequence(outcomes["outcomes"], "outcomes"):
        obj(row, "candidate_id observation", label="outcome")
        cid, obs = text(row["candidate_id"], "outcome.candidate_id"), row["observation"]
        if cid not in all_rows or cid in actual:
            raise ValidationError("unknown or duplicate outcome candidate")
        value, _ = observation(obs, goal["outcome_unit"], as_of, f"outcome.{cid}")
        if obs["kind"] == "estimated":
            raise ValidationError("estimated values are not actual outcomes")
        if window(obs.get("observation_window"), "outcome window") != window(goal["evaluation_window"], "goal window"):
            raise ValidationError("outcome horizon mismatch")
        actual[cid] = value
        kinds.add(obs["kind"])
        verified.append(obs["independently_verified"])
    if len(kinds) > 1:
        raise ValidationError("do not mix synthetic and observed outcomes in one evaluation")
    feasible = {cid: r for cid, r in all_rows.items() if r["status"] != "BLOCKED"}
    ids = sorted(feasible.keys() & actual.keys())
    if not ids:
        raise ValidationError("no feasible candidate outcomes")
    direction = goal["direction"]
    def utility(value):
        return value if direction == "maximize" else -value if direction == "minimize" else -abs(value - goal["target"])
    utilities = {cid: _number(utility(actual[cid]), "outcome utility") for cid in ids}
    baseline_metric = doc["validation"]["baseline_metric"]
    scores = {cid: feasible[cid]["score"] for cid in ids}
    baseline = {cid: feasible[cid]["metrics"][baseline_metric]["score"] for cid in ids}
    k = doc["validation"]["top_k"]
    if k > len(ids):
        raise ValidationError("top_k exceeds available feasible outcomes")
    def top_comparison(values):
        # Fractional inclusion at the K boundary removes candidate-ID tie bias.
        threshold = sorted(values.values(), reverse=True)[k - 1]
        above = [cid for cid in ids if values[cid] > threshold]
        tied = [cid for cid in ids if values[cid] == threshold]
        share = (k - len(above)) / len(tied)
        weights = {cid: 1 if cid in above else share if cid in tied else 0 for cid in ids}
        return {"inclusion_weights": weights,
                "mean_actual": math.fsum(actual[cid] * (w / k) for cid, w in weights.items()),
                "mean_utility": math.fsum(utilities[cid] * (w / k) for cid, w in weights.items())}
    composite_top, baseline_top = top_comparison(scores), top_comparison(baseline)
    mean_utility = math.fsum(v / len(ids) for v in utilities.values())
    predictions = {p["candidate_id"]: p for p in saved["predictions"]}
    predicted_ids = sorted(predictions.keys() & actual.keys())
    forecasts = None
    if predicted_ids:
        values = [actual[cid] for cid in predicted_ids]
        forecasts = {"unit": goal["outcome_unit"], "candidate_ids": predicted_ids,
                     "model": forecast_errors([predictions[cid]["value"] for cid in predicted_ids], values),
                     "declared_baseline": forecast_errors([predictions[cid]["baseline_value"] for cid in predicted_ids], values)}
    missing = sorted(all_rows.keys() - actual.keys())
    warnings = ["Descriptive holdout evaluation, not proof of validity, causality or calibrated success probability.",
                "One decision cohort is not an independent time-series validation; never tune and validate on the same outcomes."]
    if len(ids) < doc["validation"]["min_samples"]:
        warnings.append("Insufficient sample size for the declared minimum; do not claim model effectiveness.")
    if predicted_ids and len(predicted_ids) < doc["validation"]["min_samples"]:
        warnings.append("Insufficient numeric forecast samples for the declared minimum.")
    if predictions.keys() - actual.keys():
        warnings.append("Some registered predictions have no actual outcomes; forecast errors use matched records only.")
    if missing:
        warnings.append("Incomplete outcome coverage; selection/survivorship bias may distort all comparisons.")
    if kinds == {"synthetic"} or any(o["kind"] == "synthetic" for r in report["results"] for o in r["evidence"].values()):
        warnings.append("SYNTHETIC data: this is a workflow demonstration, not real validation evidence.")
    if not all(verified):
        warnings.append("Actual outcome sources are not all independently verified.")
    if any(o["kind"] == "estimated" or not o["independently_verified"]
           for r in report["results"] for o in r["evidence"].values()):
        warnings.append("Decision-time evidence includes estimated or unverified values.")
    return {"snapshot_id": saved["snapshot_id"], "sample_count": len(ids),
            "outcome_kind": next(iter(kinds)), "missing_outcomes": missing,
            "coverage": len(actual) / len(all_rows), "ranking_coverage": len(ids) / len(feasible),
            "ranking_candidate_ids": ids,
            "spearman": spearman([scores[cid] for cid in ids], [utilities[cid] for cid in ids]),
            "baseline_spearman": spearman([baseline[cid] for cid in ids], [utilities[cid] for cid in ids]),
            "top_k": {"k": k, "composite": composite_top, "baseline_metric": baseline_metric,
                      "baseline": baseline_top, "all_candidates_mean_utility": mean_utility,
                      "lift_over_all": _number(composite_top["mean_utility"] - mean_utility, "Top-K lift"),
                      "lift_over_baseline": _number(composite_top["mean_utility"] - baseline_top["mean_utility"], "baseline lift")},
            "forecasts": forecasts, "warnings": warnings, "effectiveness_claim": "not established"}
