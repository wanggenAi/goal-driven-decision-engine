"""Evaluate predictions against later outcomes measured in the SAME unit."""

from __future__ import annotations

import csv
import math
from pathlib import Path

from .engine import ValidationError, _number
from .history import forecast_errors


def evaluate_csv(path: str | Path) -> dict:
    """CSV must contain candidate_id, predicted, actual columns."""
    errors = []
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not {"candidate_id", "predicted", "actual"} <= set(reader.fieldnames or ()):
            raise ValidationError("CSV needs candidate_id,predicted,actual columns")
        seen = set()
        for row in reader:
            cid = row.get("candidate_id")
            if not cid or cid in seen:
                raise ValidationError("candidate_id missing or duplicated in evaluation")
            seen.add(cid)
            try:
                predicted, actual = float(row["predicted"]), float(row["actual"])
            except (ValueError, TypeError) as exc:
                raise ValidationError(f"{cid}: invalid prediction or outcome") from exc
            if not math.isfinite(predicted) or not math.isfinite(actual):
                raise ValidationError(f"{cid}: prediction and outcome must be finite")
            error = _number(predicted - actual, "forecast error")
            errors.append(error)
            rows.append({"candidate_id": cid, "predicted": predicted,
                         "actual": actual, "error": error})
    if not errors:
        raise ValidationError("evaluation requires at least one row")
    n = len(errors)
    return {
        "sample_count": n,
        **{key: round(value, 6) for key, value in forecast_errors(
            [r["predicted"] for r in rows], [r["actual"] for r in rows]).items()
           if key != "sample_count"},
        "rows": rows,
        "warning": "Forecasts and actuals must use the same unit, horizon, and population. Small samples are not proof of predictive validity.",
    }
