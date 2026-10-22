"""Command-line interface for scoring, validation, and forecast evaluation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .engine import ValidationError, score_document
from .evaluate import evaluate_csv


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gqde", description="Evidence-first decision support")
    commands = parser.add_subparsers(dest="command", required=True)
    score = commands.add_parser("score", help="Score candidates in a model JSON file")
    score.add_argument("input", type=Path)
    score.add_argument("--output", "-o", type=Path)
    validate = commands.add_parser("validate", help="Validate full model and evidence")
    validate.add_argument("input", type=Path)
    evaluate = commands.add_parser("evaluate", help="Evaluate numeric forecasts against outcomes")
    evaluate.add_argument("input", type=Path)
    args = parser.parse_args(argv)

    try:
        if args.command == "evaluate":
            result = evaluate_csv(args.input)
        else:
            document = json.loads(args.input.read_text(encoding="utf-8"))
            result = score_document(document)
            if args.command == "validate":
                result = {"valid": True, "candidate_count": result["candidate_count"]}
        rendered = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.command == "score" and args.output:
            args.output.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
        return 0
    except (OSError, ValueError, json.JSONDecodeError, ValidationError) as exc:
        sys.stderr.write(f"GQDE validation/error: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
