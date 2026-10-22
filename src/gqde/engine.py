"""Deterministic composite indicators with evidence and hard decision gates.

The engine ranks observed candidates, not real-world actions. It does not
independently verify sources or infer missing observations.
"""

from __future__ import annotations

import ast
from datetime import datetime
import math
import operator
from typing import Any


class ValidationError(ValueError):
    """Invalid model, observations, or unsafe arithmetic expression."""


_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_COMPARISONS = {
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
    "==": operator.eq,
    "!=": operator.ne,
}
_KINDS = {"observed", "estimated", "synthetic"}


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{label} must be a number")
    try:
        value = float(value)
    except OverflowError as exc:
        raise ValidationError(f"{label} must be finite") from exc
    if not math.isfinite(value):
        raise ValidationError(f"{label} must be finite")
    return value


def _timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise ValidationError(f"{label} must be an ISO 8601 string")
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError(f"{label} is not a valid timestamp") from exc
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValidationError(f"{label} must include a timezone")
    return instant


def _expression(expression: Any) -> tuple[ast.Expression, set[str]]:
    if not isinstance(expression, str) or not expression or len(expression) > 256:
        raise ValidationError("metric expression must be 1–256 characters")
    try:
        parsed = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValidationError(f"invalid expression: {expression}") from exc
    names: set[str] = set()

    def check(node: ast.AST, depth: int = 0) -> None:
        if depth > 24:
            raise ValidationError("expression nesting too deep")
        if isinstance(node, ast.Expression):
            check(node.body, depth + 1)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Constant):
            _number(node.value, "numeric literal")
        elif isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
            check(node.left, depth + 1)
            check(node.right, depth + 1)
        elif isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
            check(node.operand, depth + 1)
        else:
            raise ValidationError("unsafe or unsupported metric expression")

    check(parsed)
    return parsed, names


def _calculate(tree: ast.Expression, values: dict[str, float]) -> float:
    def visit(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Name):
            if node.id not in values:
                raise ValidationError(f"missing observed input: {node.id}")
            return values[node.id]
        if isinstance(node, ast.Constant):
            return _number(node.value, "literal")
        if isinstance(node, ast.UnaryOp):
            return _number(_UNARY[type(node.op)](visit(node.operand)), "result")
        if isinstance(node, ast.BinOp):
            try:
                result = _OPERATORS[type(node.op)](visit(node.left), visit(node.right))
            except ZeroDivisionError as exc:
                raise ValidationError("division by zero in metric") from exc
            return _number(result, "result")
        raise ValidationError("unsupported expression")

    return visit(tree)


def _weighted_score(items: list[tuple[float, float]]) -> float:
    total = sum(weight for _, weight in items)
    if not total or not math.isfinite(total):
        raise ValidationError("weights must have a positive finite sum")
    return _number(math.fsum(value * (weight / total) for value, weight in items), "weighted score")


def _weight(value: Any, label: str) -> float:
    result = _number(value, label)
    if result <= 0:
        raise ValidationError(f"{label} must be > 0")
    return result


def _normalize(value: float, spec: Any) -> float:
    if not isinstance(spec, dict):
        raise ValidationError("normalization spec must be an object")
    low = _number(spec.get("low"), "normalize.low")
    high = _number(spec.get("high"), "normalize.high")
    direction = spec.get("direction")
    if high <= low or direction not in ("higher", "lower"):
        raise ValidationError("normalize requires high > low and higher/lower direction")
    span = _number(high - low, "normalization span")
    fraction = (min(high, max(low, value)) - low) / span
    if direction == "lower":
        fraction = 1 - fraction
    return round(max(0.0, min(100.0, fraction * 100.0)), 6)


def score_document(document: dict[str, Any]) -> dict[str, Any]:
    """Score all candidates, rejecting invalid documents rather than filling gaps."""
    if isinstance(document, dict) and document.get("schema_version") == "2.0":
        from .model import score_model
        return score_model(document)
    if not isinstance(document, dict) or document.get("schema_version") != "1.0":
        raise ValidationError("schema_version must be 1.0")
    as_of = _timestamp(document.get("as_of"), "as_of")
    goal = document.get("goal")
    if not isinstance(goal, dict) or not all(
        isinstance(goal.get(key), str) and goal.get(key)
        for key in ("id", "description", "success_measure")
    ):
        raise ValidationError("goal requires id, description, success_measure")
    decision = document.get("decision", {})
    if not isinstance(decision, dict):
        raise ValidationError("decision must be an object")
    min_score = _number(decision.get("min_score", 70), "min_score")
    if not 0 <= min_score <= 100:
        raise ValidationError("min_score must be within 0..100")
    max_age = decision.get("max_age_hours")
    if max_age is not None and _number(max_age, "max_age_hours") <= 0:
        raise ValidationError("max_age_hours must be > 0")

    dimensions = document.get("dimensions")
    if not isinstance(dimensions, list) or not dimensions:
        raise ValidationError("dimensions must be a nonempty list")
    compiled: list[dict[str, Any]] = []
    metric_ids: set[str] = set()
    dimension_ids: set[str] = set()
    used_inputs: set[str] = set()
    for dimension in dimensions:
        if not isinstance(dimension, dict) or not isinstance(dimension.get("id"), str):
            raise ValidationError("each dimension needs an id")
        if dimension["id"] in dimension_ids:
            raise ValidationError(f"duplicate dimension: {dimension['id']}")
        dimension_ids.add(dimension["id"])
        d_weight = _weight(dimension.get("weight"), "dimension.weight")
        metrics = dimension.get("metrics")
        if not isinstance(metrics, list) or not metrics:
            raise ValidationError("each dimension needs metrics")
        compiled_metrics = []
        for metric in metrics:
            if not isinstance(metric, dict) or not isinstance(metric.get("id"), str):
                raise ValidationError("each metric needs an id")
            mid = metric["id"]
            if mid in metric_ids:
                raise ValidationError(f"duplicate metric: {mid}")
            metric_ids.add(mid)
            m_weight = _weight(metric.get("weight"), "metric.weight")
            expr, names = _expression(metric.get("expression"))
            used_inputs |= names
            _normalize(0, metric.get("normalize"))  # validate bounds before observations
            compiled_metrics.append((metric, m_weight, expr, names))
        compiled.append({"id": dimension["id"], "weight": d_weight, "metrics": compiled_metrics})

    gates = document.get("gates", [])
    if not isinstance(gates, list):
        raise ValidationError("gates must be a list")
    for gate in gates:
        if (not isinstance(gate, dict) or gate.get("metric") not in metric_ids
                or gate.get("op") not in _COMPARISONS):
            raise ValidationError("gate needs a known metric and supported operator")
        _number(gate.get("value"), "gate.value")

    candidates = document.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ValidationError("candidates must be a nonempty list")
    results = []
    seen_candidates: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, dict) or not isinstance(candidate.get("id"), str):
            raise ValidationError("each candidate needs an id")
        cid = candidate["id"]
        if not cid or cid in seen_candidates:
            raise ValidationError(f"empty or duplicate candidate id: {cid}")
        seen_candidates.add(cid)
        observations = candidate.get("observations")
        if not isinstance(observations, dict):
            raise ValidationError(f"{cid}: observations must be an object")
        values: dict[str, float] = {}
        provenance: dict[str, Any] = {}
        warnings: list[str] = []
        for name in sorted(used_inputs):
            observed = observations.get(name)
            if not isinstance(observed, dict):
                raise ValidationError(f"{cid}: missing evidence for {name}")
            values[name] = _number(observed.get("value"), f"{cid}.{name}.value")
            source = observed.get("source")
            kind = observed.get("kind")
            when = _timestamp(observed.get("observed_at"), f"{cid}.{name}.observed_at")
            if not isinstance(source, str) or not source.strip() or kind not in _KINDS:
                raise ValidationError(f"{cid}.{name}: source and valid kind required")
            age_hours = (as_of - when).total_seconds() / 3600
            if age_hours < -1e-9:
                raise ValidationError(f"{cid}.{name}: observation is after as_of")
            if kind != "observed":
                warnings.append(f"{name}: {kind} input requires real evidence")
            if max_age is not None and age_hours > float(max_age):
                warnings.append(f"{name}: stale input ({age_hours:.1f} hours old)")
            provenance[name] = {
                "value": values[name], "source": source,
                "observed_at": observed["observed_at"], "kind": kind,
            }

        metric_results: dict[str, Any] = {}
        raw_values: dict[str, float] = {}
        dimension_results: dict[str, Any] = {}
        dimension_scores = []
        for dimension in compiled:
            metric_scores = []
            for metric, weight, expression, names in dimension["metrics"]:
                raw = _calculate(expression, values)
                raw_values[metric["id"]] = raw
                normalized = _normalize(raw, metric["normalize"])
                metric_results[metric["id"]] = {
                    "value": round(raw, 6), "score": normalized,
                    "inputs": sorted(names),
                }
                metric_scores.append((normalized, weight))
            d_score = _weighted_score(metric_scores)
            dimension_results[dimension["id"]] = round(d_score, 6)
            dimension_scores.append((d_score, dimension["weight"]))

        score = round(_weighted_score(dimension_scores), 6)
        failed = []
        for gate in gates:
            raw = raw_values[gate["metric"]]
            value = _number(gate["value"], "gate.value")
            if not _COMPARISONS[gate["op"]](raw, value):
                failed.append({"metric": gate["metric"], "op": gate["op"],
                               "threshold": value, "actual": raw})
        if failed:
            status = "BLOCKED"
        elif warnings:
            status = "NEEDS_EVIDENCE"
        elif score >= min_score:
            status = "ELIGIBLE"
        else:
            status = "BELOW_THRESHOLD"
        results.append({
            "id": cid, "score": score, "status": status,
            "dimensions": dimension_results, "metrics": metric_results,
            "failed_gates": failed, "warnings": warnings,
            "evidence": provenance,
        })

    results.sort(key=lambda item: (-item["score"], item["id"]))
    return {
        "schema_version": "1.0", "goal": goal,
        "as_of": document["as_of"], "min_score": min_score,
        "candidate_count": len(results), "results": results,
        "disclaimer": "Advisory scores only; source claims are not independently verified.",
    }
