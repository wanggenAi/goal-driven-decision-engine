# Methodology and engineering decision record (v0.1)

## Intent

Turn a clearly stated objective into a reproducible decision-support process.
A candidate score is not a forecast and not evidence of earnings.

## Conceptual mapping

| Layer | Method / principle | Implemented in MVP |
| --- | --- | --- |
| Objective -> questions -> measures | GQM (Goal–Question–Metric) | Explicit goal, dimensions and metrics; question documentation is manual |
| Measurement process | ISO/IEC/IEEE 15939 concepts | Each raw observation requires value, timestamp, source and provenance; NOT standards certification |
| Composite indicators | OECD/JRC composite indicator methodology | Bounded range normalization, weighted aggregation, transparent output |
| MCDA | Multi-criteria decision analysis | Relative priority and explicit dimension weights |
| Constraint decisions | DMN-style rule separation | Hard numerical gates checked separately from score; NOT a DMN engine |
| Validation | Forecast evaluation | Separate realized-outcome comparison with MAE, RMSE and bias; does not automatically calibrate weights |

## Traceable calculation

Let x be measured values. For metric i, D_i = f_i(x).
For a larger-is-better metric with declared range [a,b]:

    N_i(D_i) = clip(100 * (D_i-a)/(b-a), 0, 100)

Smaller-is-better reverses the result. For each dimension j:

    dimension_score_j = sum(metric_weight_i * N_i(D_i)) / sum(metric_weight_i)

Overall:

    S = sum(dimension_weight_j * dimension_score_j) / sum(dimension_weight_j)

Use hard gates before acting. A blocked candidate stays blocked regardless of score.
Normalization ranges and weights are **assumptions** whose sensitivity and utility must be tested.
Relative rankings can flip when those assumptions change.

## Evidence contract

Every input used by expressions needs:

- value: finite numeric value; no bool, NaN or Infinity.
- source: human-readable origin (URL, document, export or synthetic identifier).
- observed_at: timezone-aware ISO timestamp not later than as_of.
- kind: observed, estimated, or synthetic.

"Observed" is a user assertion and is NOT automatically authenticated. Stale, estimated,
or synthetic values force NEEDS_EVIDENCE. Missing values abort the evaluation.
Use the same units, population, and observation windows within candidate comparisons.

## Validation stages before claiming real effectiveness

1. Register the precise objective and outcome horizon (e.g. 30-day realized net profit).
2. Collect lawful evidence with timestamps and source records.
3. Establish a naïve baseline and preregister candidate selection thresholds.
4. Test robustness to alternative weights, normalization ranges and missingness.
5. Compare scored candidates to later outcomes on an out-of-time holdout sample.
6. Measure decision utility, not just ranking metrics; count costs, losses and false positives.
7. Calibrate or reject formulas that fail to outperform simple baselines.

The bundled evaluate command compares numeric predictions and numeric actuals, **not** 0–100 composite scores to currency profits. It is deliberately a separate workflow.

## Scope / non-goals

No scraping, paid APIs, auto-commerce, securities trades, model-training pipeline, or frontend in v0.1.
No claim that normalization or MCDA proves causality. All sample data are synthetic.

## Primary references

- OECD/JRC Handbook on Constructing Composite Indicators:
  https://www.oecd.org/en/publications/handbook-on-constructing-composite-indicators_9789264043466-en.html
- European Commission JRC, 10-step composite indicator guide:
  https://knowledge-for-policy.ec.europa.eu/composite-indicators/toolkit_en/navigation-page/10-step-guide_en
- NASA software engineering measurement guidance:
  https://swehb.nasa.gov/
- ISO/IEC/IEEE 15939:
  https://www.iso.org/standard/71197.html
- OMG Decision Model and Notation:
  https://www.omg.org/spec/DMN/
