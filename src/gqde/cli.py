"""CLI for contracts, scoring, robustness, snapshots and outcome validation."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .analysis import sensitivity, what_if
from .engine import ValidationError, score_document
from .evaluate import evaluate_csv
from .history import evaluate_history, save_snapshot, snapshot
from .reporting import markdown


def load_json(path: Path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValidationError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    def constant(value):
        raise ValidationError(f"non-finite JSON constant: {value}")
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs, parse_constant=constant)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gqde", description="Evidence-first decision support")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in [("score", "Score candidates"), ("validate", "Validate model and evidence"),
                            ("evaluate", "Legacy numeric CSV forecast comparison (unverified units/times)"),
                            ("sensitivity", "Deterministic weight robustness"),
                            ("what-if", "Counterfactual inputs or local weights"),
                            ("snapshot", "Freeze a versioned decision; output must not exist"),
                            ("history", "Compare a frozen decision with later outcomes")]:
        command = commands.add_parser(name, help=help_text)
        command.add_argument("input", type=Path)
        command.add_argument("--output", "-o", type=Path, required=name == "snapshot")
        if name != "snapshot":
            command.add_argument("--format", choices=["json", "markdown"], default="json")
        if name in {"score", "sensitivity"}:
            command.add_argument("--delta", type=float, default=0.05)
        if name == "score":
            command.add_argument("--sensitivity", action="store_true")
        if name == "snapshot":
            command.add_argument("--predictions", type=Path)
        if name == "history":
            command.add_argument("outcomes", type=Path)
        if name == "what-if":
            command.add_argument("changes", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "evaluate":
            result = evaluate_csv(args.input)
        else:
            document = load_json(args.input)
            if args.command == "history":
                result = evaluate_history(document, load_json(args.outcomes))
            elif args.command == "snapshot":
                result = snapshot(document, load_json(args.predictions) if args.predictions else None)
                save_snapshot(result, args.output)
                sys.stdout.write(json.dumps({"snapshot_id": result["snapshot_id"], "output": str(args.output)}) + "\n")
                return 0
            elif args.command == "sensitivity":
                result = sensitivity(document, args.delta)
            elif args.command == "what-if":
                result = what_if(document, load_json(args.changes))
            else:
                result = score_document(document)
                if args.command == "validate":
                    result = {"valid": True, "schema_version": result["schema_version"], "candidate_count": result["candidate_count"]}
                elif args.sensitivity:
                    result["sensitivity"] = sensitivity(document, args.delta)
        rendered = (markdown(result) if args.format == "markdown" else
                    json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
        if args.output:
            args.output.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
        return 0
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"GQDE validation/error: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
