# Methodology and engineering decisions (0.2)

## Purpose and traceability

GQDE supports decisions about operationalizable, observable goals. It does not infer a goal from available data. A goal defines the outcome, population, context, direction and future horizon. Questions state what must be understood; metrics answer those questions; formulas consume explicit raw observations. Every metric must connect to a question and every question to the configured goal. The graph is checked, not just documented.

The implementation applies selected ideas from the primary references below. It claims neither certification nor full implementation of ISO 15939 or DMN. No reference code or external implementation was copied; the runtime uses only Python's standard library. No third-party methodology dependency or associated runtime license is needed.

## Normalization and additive MCDA

For a metric value x and **predeclared** finite anchors a < b:

```
higher: N(x) = 100 * (clip(x,a,b) - a) / (b-a)
lower:  N(x) = 100 - higher(x)
target: N(x) = 100 * max(0, 1 - abs(x-t) / tolerance)
```

Target normalization expresses a symmetric preference around t; it is suitable when departures on both sides are undesirable. It is not a one-sided saturation formula. Use higher/lower Min-Max for monotone preferences with meaningful anchors. Clip before subtraction to avoid overflow for far-outside values; reject non-finite or unrepresentable spans. Out-of-anchor metrics are flagged for review. No sample-dependent extrema are fitted: adding candidates cannot silently change anchors or existing scores.

Let d_j be the dimension weight and m_ij the local metric weight. Effective weight:

```
w_ij = (d_j / sum(d)) * (m_ij / sum_i(m_ij))
S = sum_ij(w_ij * N_ij)
contribution_ij = w_ij * N_ij
weighted_shortfall_j = sum_i(w_ij * (100 - N_ij))
```

Weights are explicit, finite, nonnegative judgments with a recorded basis and positive sums at each layer. Large weights are rescaled before summation. Zero-weight dimensions/metrics still undergo evidence and gate validation. The report identifies the dimension with the largest **weighted contribution** and largest **weighted shortfall**, not causal drivers. Values and gates retain full precision; human-readable formatting rounds only the display.

Additive MCDA assumes that preferences can be represented additively over these scales. Weights express tradeoffs over the declared scale ranges, not universal importance independent of normalization. Correlated indicators can double count evidence. Low values can be compensated by high values **within** the score. Conditions that must never be compensated belong in hard gates. No automatic optimum, independence test, alternative ranking algorithm or causal inference is claimed.

## Evidence and hard rules

Each input has an exact unit label, bounds where applicable, value, source, observed/available time, provenance kind and independent-verification assertion. Windows must end before evidence becomes available; candidates must use comparable windows for the same input. Unit conversions and expression dimensional inference are not automatic. Sources, populations and verification claims require an external measurement/audit process.

Numerical rules (`> >= < <= == !=`) are separate from aggregation and use unrounded derived values. Maximum evidence age, allowed kinds and required independent verification are also hard rules. Missing/invalid data are errors, never zeros. Synthetic/estimated/unverified evidence cannot make a candidate decision-ready. The feasible analysis population excludes BLOCKED candidates; its members can still require evidence or fail the score threshold.

## Deterministic robustness and counterfactuals

For each effective metric share w, replace it once with clip(w-delta,0,1) and once with clip(w+delta,0,1). Redistribute the remaining mass proportionally to other effective shares. If all other shares are zero, distribute it equally. Skip unchanged perturbations. The default delta is 0.05 **absolute share** (five percentage points), not five percent relative. Report requested and actual shifts, full weights, scores, changed ranks, rank ranges, top set and sensitive metrics.

Gates, normalized values and evidence are fixed during this weight experiment. Proportional redistribution may cross original dimension shares: this deliberately tests effective metric influence. It does not claim to optimize stakeholder preferences. Input or local-weight counterfactuals are a separate `what-if` workflow that rescans all formulas, evidence and hard constraints; changed inputs are explicitly synthetic.

Scores within absolute 1e-9 share a feasible rank; IDs only order their display. First-place stability is the fraction of tested perturbations retaining the same **unique** baseline winner; it is undefined if baseline is tied, no candidate is feasible or no perturbations exist. Top-set stability also supports ties. A sensitive metric is one whose perturbation changes any candidate's rank. These fractions describe this finite robustness experiment, never a probability of real success. They do not cover simultaneous perturbations or all possible parameter/data changes.

## Frozen decisions and later actuals

A snapshot preserves the complete document (including formulas, units, evidence, weights and anchors), engine/model versions, the calculated decision and optional numeric predictions/baselines. Its canonical JSON SHA-256 covers all payload fields. Files are exclusively created. Verification checks both digest and calculation replay. This protects against accidental drift, not an adversary who can rewrite all files; independent preregistration/version control is required to establish genuine decision timing.

The feature cutoff is as_of; outcome windows start at or after it. Later actual records must match the goal measure, unit and entire registered horizon, be available by the outcome evaluation as_of, and be observed or explicitly synthetic. Estimates are not actuals; observed and synthetic actuals cannot be mixed in one evaluation. These checks prevent declared temporal leakage, but cannot detect falsely backdated or revised source records.

Three different quantities remain separate:

- **Composite Score**: bounded preference aggregation, used for ranking only.
- **Prediction**: separately supplied numeric future result with its unit/method and a baseline declared before observing actuals. No automatic numeric forecast or success probability is created.
- **Actual Outcome**: later observation over the registered horizon.

For supplied same-unit predictions, report MAE = mean(abs(predicted-actual)), RMSE = sqrt(mean(error²)) and signed bias = mean(error). RMSE rescales errors before squaring to avoid unnecessary overflow. Forecast metrics use the available prediction/outcome intersection, with explicit IDs/count; ranking uses available feasible candidates. No error metric compares a 0–100 score to currency or followers.

Ranking validation uses Spearman (Pearson correlation of average ranks, handling ties; undefined for constant ranks). Minimize goals reverse outcome utility, target goals use negative distance to target. Top-K compares mean raw outcome and mean direction-aware utility of the score-selected subset, the **predeclared** baseline-metric subset and all feasible candidates with outcomes. Ties at the K boundary receive fractional inclusion so IDs cannot favor an outcome. This is descriptive decision utility, not forecast calibration.

Outcome coverage and missing candidate IDs are explicit; incomplete results warn about selection/survivorship bias. A configurable minimum sample count flags insufficiency, but even exceeding it is not evidence of effectiveness. Synthetic inputs/results always warn. A single cohort cannot establish time-series generalization. The report never automatically asserts effectiveness. Real validation requires preregistered outcomes, multiple independent future cohorts, costs and failures, a simple fixed baseline, and a holdout excluded from parameter tuning. Learning/automatic calibration is deferred until this evidence exists.

## Primary references and concrete use

- [Basili et al., Goal Question Metric](https://www.cs.umd.edu/~basili/publications/technical/T89.pdf): hierarchical goal/question/metric traceability, implemented by graph validation and report links.
- [OECD/JRC, Handbook on Constructing Composite Indicators (2008)](https://www.oecd.org/en/publications/handbook-on-constructing-composite-indicators-methodology-and-user-guide_9789264043466-en.html): explicit normalization and aggregation assumptions, documented tradeoffs, weight robustness and transparent reporting. GQDE implements a selected subset, not the whole handbook.
- [UK government, Multi-criteria analysis: a manual](https://www.gov.uk/government/publications/multi-criteria-analysis-manual-for-making-government-policy): interpretable additive preference scoring and the importance of scale-dependent weights and sensitivity.
- [ISO/IEC/IEEE 15939 public description](https://www.iso.org/standard/71197.html): information needs, measurement and validity principles inform evidence metadata and later evaluation. This work uses the public description, not a claim of normative conformance or access to the paid standard text.
- [OMG DMN 1.5](https://www.omg.org/spec/DMN/1.5/About-DMN): separation of explicit decision conditions from calculations; only simple numerical gate rules are implemented, without DMN interchange/FEEL.
- [NIST, Spearman rank correlation](https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/rankcorr.htm): Pearson correlation of ranks with average ranks for ties.
