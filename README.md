# Goal-Driven Decision Engine (GQDE)

An evidence-first, goal-driven, domain-agnostic **decision-support** engine.

目标驱动量化决策引擎：将“目标 → 评价维度 → 可计算指标 → 可追溯原始数据 → 评分 → 硬约束 → 反馈”落实为可运行、可测试的最小工程。

## Principles / 核心原则

1. **Objective first**: begin with a defined goal and success outcome; never pick metrics just because they are available.
2. **Evidence over invention**: every input must carry value, source, observation time, and observed/estimated/synthetic provenance. A reported source is traceability, **not independent verification**.
3. **Transparent math**: arithmetic expressions, bounded 0–100 normalization, explicit metric and dimension weights.
4. **Hard gates first**: a strong score never overrides a violated constraint.
5. **Fail closed**: missing data, unsafe formulas, division by zero, invalid timestamps, or bad weights produce an error, not invented values.
6. **Forecasts are not outcomes**: composite scores rank candidates; only actual outcomes can demonstrate whether a decision model works.
7. **No automatic real-world action**: results are advisory; no trading, scraping, purchases, publishing, or other external actions.

## Quick start / 快速运行

Requires Python 3.10+, with no runtime third-party packages.

    python -m pip install -e .
    gqde score examples/candidates.json --output result.json
    gqde validate examples/candidates.json
    gqde evaluate examples/outcomes.csv
    python -m unittest discover -s tests -v

You can also run without installation (from repository root):

    PYTHONPATH=src python -m gqde.cli score examples/candidates.json

The bundled candidates are **synthetic training data**, never real product opportunities or audited commercial evidence. They will be marked NEEDS_EVIDENCE even if their numeric score exceeds the threshold.

## Input model / 数据契约

- schema_version: 1.0
- as_of: timezone-aware ISO 8601 timestamp, pinned for reproducible freshness checks.
- goal: id, description, success_measure.
- decision: min_score between 0 and 100, optional max_age_hours.
- dimensions: weighted list; each has weighted metrics.
- metric: id, expression, normalize {low, high, direction: higher | lower}.
- gates: {metric, op, value}, where op is >, >=, <, <=, ==, or !=.
- candidates: id and observations mapping; each raw input needs {value, source, observed_at, kind}.
- kind: observed, estimated or synthetic. Estimated/synthetic or stale inputs require human evidence review.

Expressions allow only numeric constants, input variable names, parentheses, unary +/- and arithmetic + - * /. There is **no eval**, no functions, no attribute access, and no external code execution.

## Decision statuses

- BLOCKED: one or more hard gates failed.
- NEEDS_EVIDENCE: estimated, synthetic, or stale inputs; not decision-ready.
- ELIGIBLE: sufficient score, all gates passed, inputs marked observed. Does **not** mean guaranteed success.
- BELOW_THRESHOLD: valid evidence and gates, but score under configured threshold.

The program cannot verify that a claimed "observed" source is truthful; source audits remain a separate step. Norm ranges and weights are modeling assumptions, **not empirically learned** in this MVP.

## Methodology & next steps

Read docs/METHODOLOGY.md. Inspired by GQM, the OECD/JRC composite-indicator framework, ISO/IEC/IEEE 15939 measurement principles, and MCDA. **Not** an ISO-certified or official implementation of those standards.

MVP intentionally excludes automated data collection, ML prediction, adaptive weights, web dashboard, and deployment infrastructure. First gather outcome data and test whether scores correlate with realized results before adding complexity.
