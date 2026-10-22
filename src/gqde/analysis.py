"""Deterministic, one-at-a-time effective-weight robustness and input scenarios."""
from __future__ import annotations

import copy
import math

from .engine import ValidationError, _number, score_document
from .model import obj, shares


def ranking(scores: dict[str, float]) -> dict:
    ordered = sorted(scores, key=lambda k: (-scores[k], k))
    ranks = {cid: 1 + sum(value > scores[cid] and not math.isclose(value, scores[cid], abs_tol=1e-9, rel_tol=0)
                          for value in scores.values()) for cid in ordered}
    return {"order": ordered, "ranks": ranks, "winners": sorted(cid for cid in ordered if ranks[cid] == 1)}


def sensitivity(document: dict, delta: float = 0.05) -> dict:
    """Move one effective share +/- delta, rescale the rest proportionally.

    If all other shares are zero, distribute their new mass equally. Gates and
    evidence remain fixed. Ties share a rank; IDs only order their display.
    """
    delta = _number(delta, "delta")
    if not 0 < delta < 1:
        raise ValidationError("delta must be within (0,1)")
    report = score_document(document)
    if report["schema_version"] != "2.0":
        raise ValidationError("sensitivity requires schema 2.0; migrate explicitly")
    weights = report["effective_weights"]
    feasible = [r for r in report["results"] if r["status"] != "BLOCKED"]
    baseline = ranking({r["id"]: r["score"] for r in feasible})
    scenarios, impacts = [], {}
    rank_ranges = {cid: [rank] for cid, rank in baseline["ranks"].items()}
    if len(weights) > 1:
        for mid, weight in sorted(weights.items()):
            changed_count = 0
            for sign in (-1, 1):
                updated = min(1, max(0, weight + sign * delta))
                if updated == weight:
                    continue
                others = {m: w for m, w in weights.items() if m != mid}
                proportions = shares(others) if any(others.values()) else {m: 1 / len(others) for m in others}
                perturbed = {m: w * (1 - updated) for m, w in proportions.items()}
                perturbed[mid] = updated
                scores = {r["id"]: math.fsum(r["metrics"][m]["score"] * w for m, w in perturbed.items()) for r in feasible}
                ranks = ranking(scores)
                changed = [cid for cid in baseline["order"] if ranks["ranks"][cid] != baseline["ranks"][cid]]
                for cid, rank in ranks["ranks"].items():
                    rank_ranges[cid].append(rank)
                changed_count += bool(changed)
                scenarios.append({"metric": mid, "requested_delta": sign * delta,
                                  "actual_delta": updated - weight, "effective_weights": perturbed,
                                  "scores": scores, **ranks, "changed_candidates": changed,
                                  "top_set_unchanged": ranks["winners"] == baseline["winners"]})
            impacts[mid] = changed_count
    n = len(scenarios)
    unique = len(baseline["winners"]) == 1
    return {"analysis": "model robustness, not success probability", "delta": delta,
            "method": "One effective metric share at a time; proportional redistribution; fixed gates and evidence.",
            "baseline": baseline, "scenario_count": n, "scenarios": scenarios,
            "first_place_stability": (sum(s["winners"] == baseline["winners"] for s in scenarios) / n if n and unique else None),
            "top_set_stability": sum(s["top_set_unchanged"] for s in scenarios) / n if n and feasible else None,
            "rank_ranges": {cid: {"best": min(ranks), "worst": max(ranks)} for cid, ranks in rank_ranges.items()},
            "sensitive_metrics": [{"metric": m, "rank_changing_scenarios": count} for m, count in
                                  sorted(impacts.items(), key=lambda pair: (-pair[1], pair[0])) if count],
            "warnings": (["Baseline has no unique feasible winner; first-place stability is undefined."] if not unique else []) +
                        ["A finite perturbation grid is not a guarantee over all possible weights or data errors."]}


def what_if(document: dict, changes: dict) -> dict:
    """Counterfactual input values and/or LOCAL metric weights; never mutate evidence."""
    original = score_document(document)
    if original["schema_version"] != "2.0":
        raise ValidationError("what-if requires schema 2.0")
    obj(changes, "", "candidate_id inputs metric_weights", "changes")
    modified = copy.deepcopy(document)
    inputs = changes.get("inputs", {})
    weights = changes.get("metric_weights", {})
    if not isinstance(inputs, dict) or not isinstance(weights, dict) or not (inputs or weights):
        raise ValidationError("changes needs nonempty inputs or metric_weights objects")
    if inputs:
        candidates = {c["id"]: c for c in modified["candidates"]}
        cid = changes.get("candidate_id")
        if not isinstance(cid, str) or cid not in candidates:
            raise ValidationError("changes needs known candidate_id")
        for name, value in inputs.items():
            if name not in modified["inputs"]:
                raise ValidationError("unknown input in changes")
            obs = candidates[cid]["observations"][name]
            obs.update(value=_number(value, name), kind="synthetic", independently_verified=False,
                       source="synthetic:counterfactual")
    metrics = {m["id"]: m for d in modified["dimensions"] for m in d["metrics"]}
    for mid, weight in weights.items():
        if mid not in metrics:
            raise ValidationError("unknown metric weight in changes")
        metrics[mid]["weight"] = _number(weight, mid)
        metrics[mid]["weight_basis"] = "Counterfactual local weight override"
    updated = score_document(modified)
    old = {r["id"]: r for r in original["results"]}
    return {"analysis": "counterfactual, not observed evidence", "changes": copy.deepcopy(changes),
            "score_changes": {r["id"]: {"before": old[r["id"]]["score"], "after": r["score"],
                                          "delta": r["score"] - old[r["id"]]["score"],
                                          "status_before": old[r["id"]]["status"], "status_after": r["status"]}
                              for r in updated["results"]}, "report": updated}
