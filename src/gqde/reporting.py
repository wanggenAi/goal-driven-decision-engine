"""Human-readable reports backed by the same structured JSON results."""
from __future__ import annotations

import json


def cell(value) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def markdown(report: dict) -> str:
    if "results" not in report:
        title = report.get("analysis", "GQDE analysis report")
        return f"# {cell(title)}\n\n```json\n{json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)}\n```\n"
    lines = ["# GQDE decision report", "", report["goal"]["description"], "",
             f"As of: {report['as_of']}. Composite scores are not success probabilities.", "",
             "| Candidate | Score | Status | Feasible rank |", "| --- | ---: | --- | ---: |"]
    for row in report["results"]:
        lines.append(f"| {cell(row['id'])} | {row['score']:.4f} | {row['status']} | {row.get('rank', 'legacy')} |")
    if "questions" in report:
        lines += ["", "Goal → Question → Metric:", ""]
        lines += [f"- {cell(q['goal_id'])} → {cell(q['id'])}: {cell(q['question'])} → {cell(', '.join(q['metrics']))}."
                  for q in report["questions"]]
    for row in report["results"]:
        lines += ["", f"## {cell(row['id'])}", "", row.get("recommendation", "Review evidence and constraints."), ""]
        if "largest_contribution" in row:
            lines += [f"Largest weighted contribution: {cell(row['largest_contribution'])}. "
                      f"Largest weighted shortfall: {cell(row['main_weakness'])}.", ""]
        lines += ["| Metric | Raw value | Unit | Normalized | Effective weight | Contribution | Questions |",
                  "| --- | ---: | --- | ---: | ---: | ---: | --- |"]
        for mid, metric in row["metrics"].items():
            lines.append(f"| {cell(mid)} | {metric['value']:.6g} | {cell(metric.get('unit', 'legacy'))} | "
                         f"{metric['score']:.4f} | {metric.get('effective_weight', 0):.4f} | "
                         f"{metric.get('contribution', 0):.4f} | {cell(', '.join(metric.get('question_ids', [])))} |")
        lines += ["", "Calculation and evidence:", ""]
        for mid, metric in row["metrics"].items():
            if "expression" in metric:
                lines.append(f"- {cell(mid)} = `{cell(metric['expression'])}`; {cell(metric['explanation'])}. "
                             f"Normalization: {cell(json.dumps(metric['normalization'], ensure_ascii=False))}. "
                             f"Local weight={metric['local_weight']}; basis={cell(metric['weight_basis'])}.")
        for name, obs in row["evidence"].items():
            lines.append(f"- {cell(name)}: {obs['value']} {cell(obs.get('unit', ''))}; "
                         f"source={cell(obs['source'])}; observed_at={obs['observed_at']}; kind={obs['kind']}; "
                         f"independently_verified={obs.get('independently_verified', 'not recorded')}; "
                         f"window={cell(json.dumps(obs.get('observation_window'), ensure_ascii=False))}.")
        lines += ["", "Failed hard constraints: " + cell(json.dumps(row["failed_gates"], ensure_ascii=False)), ""]
        lines += [f"- {cell(warning)}" for warning in row["warnings"]]
    lines += ["", "## Uncertainties", ""]
    lines += [f"- {cell(warning)}" for warning in report.get("uncertainties", [report["disclaimer"]])]
    if "sensitivity" in report:
        robust = report["sensitivity"]
        lines += ["", "## Weight robustness", "", "Model robustness, not success probability.", "",
                  f"First-place stability: {robust['first_place_stability']}; scenarios: {robust['scenario_count']}.", "",
                  "```json", json.dumps(robust, ensure_ascii=False, indent=2), "```"]
    return "\n".join(lines) + "\n"
