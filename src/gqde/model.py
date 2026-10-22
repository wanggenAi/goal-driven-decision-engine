"""Version 2 GQM contract and traceable, domain-independent weighted MCDA.

Unit symbols are exact labels: no implicit conversions or dimensional inference.
All numeric decisions use full precision; presentation may round separately.
"""
from __future__ import annotations

import copy
import math
from typing import Any

from .engine import (ValidationError, _number, _timestamp, _expression, _calculate,
                     _COMPARISONS, _KINDS)

ENGINE_VERSION = "0.2.0"


def obj(value: Any, required: str, optional: str = "", label: str = "object") -> dict:
    if not isinstance(value, dict):
        raise ValidationError(f"{label} must be an object")
    missing = set(required.split()) - value.keys()
    unknown = value.keys() - set((required + " " + optional).split())
    if missing or unknown:
        raise ValidationError(f"{label}: missing {sorted(missing)}, unknown {sorted(unknown)}")
    return value


def text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{label} must be a nonempty string")
    return value


def sequence(value: Any, label: str) -> list:
    if not isinstance(value, list) or not value:
        raise ValidationError(f"{label} must be a nonempty list")
    return value


def boolean(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{label} must be boolean")
    return value


def window(value: Any, label: str) -> tuple:
    obj(value, "start end", label=label)
    start, end = (_timestamp(value[k], f"{label}.{k}") for k in ("start", "end"))
    if end <= start:
        raise ValidationError(f"{label}: end must be after start")
    return start, end


def shares(values: dict[str, float]) -> dict[str, float]:
    # Rescale first to avoid overflow when otherwise valid large weights are used.
    for key, value in values.items():
        if _number(value, f"weight {key}") < 0:
            raise ValidationError("weights must be nonnegative")
    scale = max(values.values(), default=0)
    if scale <= 0:
        raise ValidationError("weights must have a positive sum")
    scaled = {k: v / scale for k, v in values.items()}
    total = math.fsum(scaled.values())
    return {k: v / total for k, v in scaled.items()}


def normalize(value: float, spec: dict, direction: str) -> float:
    _number(value, "metric value")
    method = spec.get("method") if isinstance(spec, dict) else None
    if method == "min_max":
        obj(spec, "method low high basis", label="normalize")
        low, high = (_number(spec[k], f"normalize.{k}") for k in ("low", "high"))
        span = _number(high - low, "normalization span")
        if span <= 0 or direction not in ("higher", "lower"):
            raise ValidationError("min_max requires high > low and higher/lower direction")
        # Clip BEFORE arithmetic, preventing overflow for out-of-range inputs.
        fraction = (min(high, max(low, value)) - low) / span
        if direction == "lower":
            fraction = 1 - fraction
    elif method == "target":
        obj(spec, "method target tolerance basis", label="normalize")
        target = _number(spec["target"], "normalize.target")
        tolerance = _number(spec["tolerance"], "normalize.tolerance")
        if tolerance <= 0 or direction != "target":
            raise ValidationError("target normalization needs target direction and positive tolerance")
        distance = abs(value - target)
        fraction = 0 if not math.isfinite(distance) else max(0, 1 - distance / tolerance)
    else:
        raise ValidationError("normalize.method must be min_max or target")
    text(spec["basis"], "normalization basis")
    return 100 * fraction


def validate_model(document: dict) -> dict:
    """Validate the model graph before reading any candidate evidence."""
    obj(document, "schema_version model_version as_of goal questions inputs dimensions gates decision candidates validation",
        label="document")
    if document["schema_version"] != "2.0":
        raise ValidationError("schema_version must be 2.0")
    text(document["model_version"], "model_version")
    as_of = _timestamp(document["as_of"], "as_of")
    goal = obj(document["goal"], "id description success_measure evaluation_window direction object context outcome_unit",
               "target", "goal")
    for key in ("id", "description", "success_measure", "object", "context", "outcome_unit"):
        text(goal[key], f"goal.{key}")
    start, _ = window(goal["evaluation_window"], "goal.evaluation_window")
    if start < as_of:
        raise ValidationError("goal evaluation window must start at or after as_of")
    if goal["direction"] not in ("maximize", "minimize", "target"):
        raise ValidationError("goal.direction must be maximize, minimize or target")
    if goal["direction"] == "target":
        _number(goal.get("target"), "goal.target")
    elif "target" in goal:
        raise ValidationError("goal.target requires target direction")
    inputs = document["inputs"]
    if not isinstance(inputs, dict) or not inputs:
        raise ValidationError("inputs must be a nonempty object")
    for name, spec in inputs.items():
        if not isinstance(name, str) or not name.isidentifier():
            raise ValidationError("input names must be identifiers")
        obj(spec, "unit description", "min max", f"input {name}")
        text(spec["unit"], "input unit")
        text(spec["description"], "input description")
        for key in ("min", "max"):
            if key in spec:
                _number(spec[key], f"input.{key}")
        if spec.get("min", -math.inf) > spec.get("max", math.inf):
            raise ValidationError("input min exceeds max")
    dims, metrics, trees, used = {}, {}, {}, set()
    for dimension in sequence(document["dimensions"], "dimensions"):
        obj(dimension, "id weight weight_basis metrics", label="dimension")
        did = text(dimension["id"], "dimension id")
        if did in dims:
            raise ValidationError("duplicate dimension id")
        dims[did] = dimension
        text(dimension["weight_basis"], "dimension weight_basis")
        for metric in sequence(dimension["metrics"], "metrics"):
            obj(metric, "id expression inputs unit direction normalize weight weight_basis explanation evidence_requirements",
                label="metric")
            mid = text(metric["id"], "metric id")
            if mid in metrics:
                raise ValidationError("duplicate metric id")
            metrics[mid] = metric
            tree, names = _expression(metric["expression"])
            declared = sequence(metric["inputs"], "metric.inputs")
            if any(not isinstance(n, str) for n in declared) or len(set(declared)) != len(declared):
                raise ValidationError("metric inputs must be unique names")
            if set(declared) != names or not names <= inputs.keys():
                raise ValidationError("expression inputs must match declared, known inputs")
            used |= names
            trees[mid] = tree
            for key in ("unit", "weight_basis", "explanation"):
                text(metric[key], f"metric.{key}")
            normalize(0, metric["normalize"], metric["direction"])
            evidence = obj(metric["evidence_requirements"],
                           "allowed_kinds independently_verified max_age_hours window_required", label="evidence_requirements")
            kinds = sequence(evidence["allowed_kinds"], "allowed_kinds")
            if any(not isinstance(k, str) or k not in _KINDS for k in kinds):
                raise ValidationError("invalid allowed_kinds")
            for key in ("independently_verified", "window_required"):
                boolean(evidence[key], key)
            if _number(evidence["max_age_hours"], "max_age_hours") <= 0:
                raise ValidationError("max_age_hours must be positive")
        shares({m["id"]: m["weight"] for m in dimension["metrics"]})
    if used != inputs.keys():
        raise ValidationError("every declared input must be used by a metric")
    dshares = shares({k: v["weight"] for k, v in dims.items()})
    effective = {}
    for did, dimension in dims.items():
        for mid, share in shares({m["id"]: m["weight"] for m in dimension["metrics"]}).items():
            effective[mid] = dshares[did] * share
    questions, covered = {}, set()
    for question in sequence(document["questions"], "questions"):
        obj(question, "id goal_id question metrics", label="question")
        qid = text(question["id"], "question id")
        if qid in questions or question["goal_id"] != goal["id"]:
            raise ValidationError("duplicate question or unknown goal_id")
        text(question["question"], "question")
        mids = sequence(question["metrics"], "question.metrics")
        if any(not isinstance(m, str) or m not in metrics for m in mids) or len(mids) != len(set(mids)):
            raise ValidationError("question must reference unique known metrics")
        covered.update(mids)
        questions[qid] = question
    if covered != metrics.keys():
        raise ValidationError("every metric must be traced to a goal question")
    decision = obj(document["decision"], "min_score", label="decision")
    if not 0 <= _number(decision["min_score"], "min_score") <= 100:
        raise ValidationError("min_score must be within 0..100")
    if not isinstance(document["gates"], list):
        raise ValidationError("gates must be a list")
    gate_ids = set()
    for gate in document["gates"]:
        obj(gate, "id metric op value explanation", label="gate")
        gid = text(gate["id"], "gate id")
        if (gid in gate_ids or not isinstance(gate["metric"], str) or gate["metric"] not in metrics
                or not isinstance(gate["op"], str) or gate["op"] not in _COMPARISONS):
            raise ValidationError("gate needs unique id, known metric and supported operator")
        gate_ids.add(gid)
        _number(gate["value"], "gate.value")
        text(gate["explanation"], "gate explanation")
    validation = obj(document["validation"], "baseline_metric top_k min_samples", label="validation")
    if not isinstance(validation["baseline_metric"], str) or validation["baseline_metric"] not in metrics:
        raise ValidationError("unknown baseline_metric")
    for key in ("top_k", "min_samples"):
        n = validation[key]
        if isinstance(n, bool) or not isinstance(n, int) or n < (3 if key == "min_samples" else 1):
            raise ValidationError(f"validation.{key} is invalid")
    return {"metrics": metrics, "dimensions": dims, "trees": trees, "weights": effective,
            "questions": questions, "as_of": as_of}


def observation(value: Any, unit: str, as_of, label: str) -> tuple[float, float]:
    obj(value, "value unit source observed_at kind independently_verified", "observation_window", label)
    number = _number(value["value"], label)
    if value["unit"] != unit:
        raise ValidationError(f"{label}: unit mismatch; expected {unit}")
    text(value["source"], f"{label}.source")
    if not isinstance(value["kind"], str) or value["kind"] not in _KINDS:
        raise ValidationError(f"{label}: invalid kind")
    verified = boolean(value["independently_verified"], "independently_verified")
    if value["kind"] == "synthetic" and verified:
        raise ValidationError("synthetic data cannot be independently verified real evidence")
    when = _timestamp(value["observed_at"], f"{label}.observed_at")
    age = (as_of - when).total_seconds() / 3600
    if age < 0:
        raise ValidationError(f"{label}: observation is after as_of")
    if "observation_window" in value:
        _, end = window(value["observation_window"], f"{label}.observation_window")
        if end > when:
            raise ValidationError("observation window ends after observed_at")
    return number, age


def score_model(document: dict) -> dict:
    compiled = validate_model(document)
    results, ids, windows = [], set(), {}
    for candidate in sequence(document["candidates"], "candidates"):
        obj(candidate, "id observations", label="candidate")
        cid = text(candidate["id"], "candidate id")
        if cid in ids:
            raise ValidationError("duplicate candidate id")
        ids.add(cid)
        evidence = candidate["observations"]
        if not isinstance(evidence, dict) or evidence.keys() != document["inputs"].keys():
            raise ValidationError(f"{cid}: missing evidence or undeclared observations")
        values, ages = {}, {}
        for name, spec in document["inputs"].items():
            value, age = observation(evidence[name], spec["unit"], compiled["as_of"], f"{cid}.{name}")
            if not spec.get("min", -math.inf) <= value <= spec.get("max", math.inf):
                raise ValidationError(f"{cid}.{name}: value outside declared input range")
            # Compare the same measure over the same population window across candidates.
            observed_window = evidence[name].get("observation_window")
            canonical = window(observed_window, name) if observed_window else None
            if name in windows and windows[name] != canonical:
                raise ValidationError(f"incomparable observation windows for {name}")
            windows[name] = canonical
            values[name], ages[name] = value, age
        metric_results, failures, warnings = {}, [], []
        for mid, metric in compiled["metrics"].items():
            raw = _calculate(compiled["trees"][mid], values)
            normalized = normalize(raw, metric["normalize"], metric["direction"])
            req = metric["evidence_requirements"]
            for name in metric["inputs"]:
                obs = evidence[name]
                if obs["kind"] not in req["allowed_kinds"]:
                    failures.append({"rule": "allowed_kinds", "metric": mid, "input": name})
                if ages[name] > req["max_age_hours"]:
                    failures.append({"rule": "max_age_hours", "metric": mid, "input": name,
                                     "actual": ages[name], "threshold": req["max_age_hours"]})
                if req["independently_verified"] and not obs["independently_verified"]:
                    failures.append({"rule": "independently_verified", "metric": mid, "input": name})
                if req["window_required"] and "observation_window" not in obs:
                    raise ValidationError(f"{cid}.{name}: observation_window required")
                if obs["kind"] != "observed" or not obs["independently_verified"]:
                    warnings.append(f"{name}: {obs['kind']}; independent verification={obs['independently_verified']}")
            weight = compiled["weights"][mid]
            metric_results[mid] = {"value": raw, "unit": metric["unit"], "score": normalized,
                                   "effective_weight": weight, "contribution": normalized * weight,
                                   "expression": metric["expression"], "inputs": list(metric["inputs"]),
                                   "local_weight": metric["weight"], "weight_basis": metric["weight_basis"],
                                   "evidence_requirements": copy.deepcopy(req),
                                   "normalization": copy.deepcopy(metric["normalize"]), "explanation": metric["explanation"],
                                   "question_ids": [q for q, spec in compiled["questions"].items() if mid in spec["metrics"]]}
            if (metric["normalize"]["method"] == "min_max" and
                    not metric["normalize"]["low"] <= raw <= metric["normalize"]["high"]):
                warnings.append(f"{mid}: normalization clipped outside declared anchors")
        for gate in document["gates"]:
            raw = metric_results[gate["metric"]]["value"]
            if not _COMPARISONS[gate["op"]](raw, gate["value"]):
                failures.append({**gate, "rule": "metric_gate", "actual": raw})
        dimensions = {}
        dimension_shares = shares({did: d["weight"] for did, d in compiled["dimensions"].items()})
        for did, dimension in compiled["dimensions"].items():
            local = shares({m["id"]: m["weight"] for m in dimension["metrics"]})
            dimensions[did] = {"weight": dimension["weight"], "effective_weight": dimension_shares[did],
                               "weight_basis": dimension["weight_basis"],
                               "score": math.fsum(metric_results[m]["score"] * w for m, w in local.items()),
                               "contribution": math.fsum(metric_results[m]["contribution"] for m in local),
                               "weighted_shortfall": math.fsum((100 - metric_results[m]["score"]) * compiled["weights"][m] for m in local)}
        score = math.fsum(m["contribution"] for m in metric_results.values())
        status = ("BLOCKED" if failures else "NEEDS_EVIDENCE" if warnings else
                  "ELIGIBLE" if score >= document["decision"]["min_score"] else "BELOW_THRESHOLD")
        results.append({"id": cid, "score": score, "status": status, "metrics": metric_results,
                        "dimensions": dimensions, "failed_gates": failures,
                        "warnings": sorted(set(warnings)), "evidence": copy.deepcopy(evidence),
                        "largest_contribution": max(dimensions, key=lambda d: (dimensions[d]["contribution"], d)),
                        "main_weakness": max(dimensions, key=lambda d: (dimensions[d]["weighted_shortfall"], d)),
                        "recommendation": {"BLOCKED": "Resolve failed hard constraints before selection.",
                                           "NEEDS_EVIDENCE": "Obtain and audit real evidence before committing resources.",
                                           "ELIGIBLE": "Consider a bounded pilot and register its outcomes.",
                                           "BELOW_THRESHOLD": "Deprioritize under the declared threshold."}[status]})
    results.sort(key=lambda r: (-r["score"], r["id"]))
    feasible = [r for r in results if r["status"] != "BLOCKED"]
    for row in results:
        row["rank"] = (None if row["status"] == "BLOCKED" else
                       1 + sum(r["score"] > row["score"] and not math.isclose(r["score"], row["score"], abs_tol=1e-9, rel_tol=0)
                               for r in feasible))
    return {"schema_version": "2.0", "engine_version": ENGINE_VERSION,
            "model_version": document["model_version"], "as_of": document["as_of"],
            "goal": copy.deepcopy(document["goal"]), "questions": copy.deepcopy(document["questions"]),
            "effective_weights": compiled["weights"], "candidate_count": len(results),
            "results": results, "ranking_population": "All candidates passing hard constraints; evidence status must also be reviewed.",
            "uncertainties": ["Composite score is not a prediction or a success probability.",
                              "Weights and normalization anchors are declared judgments, not learned optima.",
                              "Source and verification flags are assertions requiring external audit.",
                              "Correlated indicators can double-count evidence; additive scoring permits compensation within hard gates."],
            "disclaimer": "Decision support only; synthetic examples cannot establish real-world validity."}
