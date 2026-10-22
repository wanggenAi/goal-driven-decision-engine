# Executed synthetic examples

Executed from the repository using `PYTHONPATH=src python examples/run_examples.py --output-dir /tmp/gqde-phase2-evidence` during phase-two acceptance. GitHub Actions repeats the same script and uploads the JSON/Markdown reports, decision snapshots, outcome evaluations and counterfactual output as workflow artifacts for each supported Python version.

**Every input, forecast, baseline and later outcome below is synthetic. The future outcome dates demonstrate a hypothetical lifecycle, not real business performance.**

## Business opportunity example

| Candidate | Composite score | Feasible rank | Status |
| --- | ---: | ---: | --- |
| business-B | 71 | 1 | NEEDS_EVIDENCE |
| business-C | 69.5 | 2 | NEEDS_EVIDENCE |
| business-A | 62.5 | 3 | NEEDS_EVIDENCE |
| business-D | 60 | none | BLOCKED |

For B, `unit_profit = 50 - 20 - 5 = 25 CNY/unit`. With fixed [0,50] anchors it normalizes to 50. Growth is `180/100 - 1 = 0.8`, normalized to 80; refund rate `1/100 = 0.01` normalizes inversely to 95 over [0,0.2]; competition 0.2 normalizes inversely to 80 over [0,1]. Effective shares are 0.40, 0.25, 0.20, 0.15, respectively:

```
S_B = 50*0.40 + 80*0.25 + 95*0.20 + 80*0.15 = 71
```

Risk contributes 31 points, the largest dimension contribution; economics has the largest weighted shortfall (20 points). Raw observations, synthetic source IDs, units, timestamps, windows and verification assertions appear in both JSON and Markdown.

Increasing the effective profit share from 40% to 45% and proportionally reducing other shares changes B to 69.25 and C to 70.375: C becomes first. Across eight deterministic +/- five-percentage-point perturbations, B remains unique first in six: stability 0.75. Growth and profit are identified as sensitive. **0.75 is a robustness fraction, not a success probability.**

D fails the positive-margin gate (`20-25-5 = -10`); a high score on its other indicators cannot restore its feasible rank. Changing B's fees to 35 through `what-if` also yields a negative margin and BLOCKED.

Synthetic later net-profit outcomes are A=900, B=600, C=1200, D=-200 CNY over the registered 30-day window. Among the three feasible candidates, composite-score Spearman is -0.5, while the prior-declared profit-only baseline is +0.5. Top-1 composite selection realizes 600 versus baseline 900: lift **-300 CNY**. The engine reports the unfavorable result rather than asserting success.

Separately supplied numeric forecasts (not the scores) have MAE=100 CNY, RMSE≈122.474487 CNY and bias=+50 CNY across four candidates. The declared constant historical-reference forecast has MAE=425 CNY. Both prediction and ranking cohorts are explicit. Three feasible samples are below the configured minimum of ten; synthetic data cannot demonstrate real validity regardless of the error metrics.

## Content strategy example

Same `score_document`, `sensitivity`, `snapshot` and `evaluate_history` functions; only the JSON configuration changes. Metrics measure exposure, interaction and follower conversion, cost and distance from a target production effort. Budget is an independent hard gate.

| Candidate | Score | Status |
| --- | ---: | --- |
| content-B | 72.875 | NEEDS_EVIDENCE |
| content-C | 57 | NEEDS_EVIDENCE |
| content-A | 55.5 | NEEDS_EVIDENCE |
| content-D | 45 | BLOCKED |

B stays unique first across all ten tested perturbations (1.0); a lower-rank reversal still identifies cadence as sensitive. Its synthetic outcome ranking has Spearman 1.0 and Top-1 lift +300 followers versus the exposure-only baseline. The report still states effectiveness **not established**, flags synthetic data and insufficient samples, and makes no success-probability claim.
