# Phase-two acceptance record

## Baseline inspection

On 2026-10-22 (Asia/Shanghai), `git ls-remote ... refs/heads/main` and `git fetch origin main` independently confirmed main at `6555bb0a4ab90ccf3edba4eb3eb4f48eb558b987`; the previously supplied short SHA was not assumed current. The workspace initially had an empty local Git repository; the remote main was checked out on `feature/phase-two` without overwriting existing source changes.

Read README, docs/METHODOLOGY.md, all four original source modules, both original test modules, both original fixtures and .github/workflows/ci.yml. Baseline command `python3 -m unittest discover -s tests -v` passed **12 tests** on Python 3.14.6.

Correct existing components retained: bounded arithmetic AST without eval, deterministic scoring, explicit hierarchical weights, observed/estimated/synthetic provenance, pinned as_of, independent numerical gates, basic CLI, CSV forecast evaluation and the standard-library-only runtime.

Identified defects fixed: legacy gates used values rounded to six decimals (could reject a small positive margin or accept a threshold violation); finite extreme normalization spans could overflow; avoidable large-weight and RMSE squaring overflow; integer-to-float overflow now raises a controlled ValidationError. None of the original tests was removed or relaxed.

## Acceptance evidence

The final local suite passed **120 tests** on Python 3.12 (installed editable package), and Python 3.14.6. A separate exhaustive probe made **1,068** malformed-field substitutions with no unexpected exception types. The full two-domain example run saved artifacts under `/tmp/gqde-phase2-evidence`; the business snapshot ID is `5653d5b516a5c26339087df2a5cd8d5fd13ef0815fc7d272f1966a60ca397369`.

The automated suite covers the GQM graph, model/input schema, metadata and time cutoffs, exact units, abnormal data, safe expressions, all normalization strategies, weight boundaries, unrounded gates, deterministic sensitivity, ties/feasible rankings, counterfactual gate rechecks, snapshot integrity/replay, later outcome units/horizons, forecasts, ranking/baseline/Top-K validation and both independent domains. Additional malformed-field probes exercise the schema's fail-closed paths.

The workflow tests Python 3.10, 3.11, 3.12, 3.13 and 3.14, runs legacy CLI commands, the full new CLI lifecycle, compilation and both example workflows. Each matrix job uploads real execution artifacts. The final delivery message records the actual final test count, main commit and completed workflow URL; a green workflow must correspond to that commit, not an earlier branch or SHA.

## Deliberate limits

- No real-world effectiveness claim: no real outcome dataset or independent prospective experiment was supplied.
- No ML, automatic optimal weights, prediction probabilities or automatic calibration; numeric forecasts remain explicit optional inputs.
- No alternative outranking/TOPSIS method, simultaneous global sensitivity, normalization-anchor sweep, confidence intervals or multiple-cohort temporal backtesting.
- No implicit unit conversion, dimensional algebra, authenticity verification, trusted timestamp service, automatic population comparability or regulatory attestation.
- Snapshots preserve and replay this engine release; future releases must explicitly retain older semantics or replay using the recorded release.
- No frontend, data acquisition/scraping, paid service, database, distributed infrastructure or automatic business/trade execution.

The highest-value next step is a preregistered, independently audited prospective pilot: freeze criteria and a simple baseline, collect full outcomes for multiple later cohorts (including failures), and evaluate held-out decision utility before calibrating weights.
