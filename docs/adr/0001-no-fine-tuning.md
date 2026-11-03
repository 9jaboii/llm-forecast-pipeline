# 0001 — Calibrate, don't fine-tune

## Status
Accepted

## Context
Forecasting accuracy could in principle be improved by fine-tuning a model
on resolved question/outcome pairs. This project chooses not to.

## Decision
Use Claude as-is via the Anthropic API or Amazon Bedrock. The only fitting
step is a small calibrator (Platt scaling or isotonic regression, chosen by
`calibration.choose_method()` based on how much resolved history exists)
that corrects the model's raw probability, not the model itself.

## Reasoning
- Fine-tuning needs thousands of resolved questions this project doesn't
  have in its first months.
- A fine-tuned model is a new artifact to secure, store, and version —
  another thing that can leak or drift silently.
- Most of the realistic gain for a forecasting task comes from prompting,
  sampling (`FC_SAMPLES` + median aggregation), retrieval (`retrieval.py`'s
  leakage-safe article selection), and calibration — all cheap, inspectable,
  and reversible. A calibrator is two to a few hundred numbers in a JSON
  file (`models/calibrator.json`); a fine-tuned model is not.
- Calibration is auditable: every forecast stores `raw_prob`,
  `calibrated_prob`, and `calibrator_version`, so any prediction can be
  traced to the exact correction applied at that time.

## Consequences
- Forecasting skill is bounded by the base model plus retrieval quality —
  there's no path to squeeze out more accuracy by training a bespoke model
  later without revisiting this decision.
- When the model or prompt changes, the old calibrator no longer applies;
  `PROMPT_VERSION` bumps and a fresh calibrator is required (see
  `src/forecaster/calibration.py` and `pipeline.calibrate`).
