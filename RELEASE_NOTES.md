# J-GameLQA v1.0

Release date: 2026-09-04

## Features

- Six deterministic Rule Checkers for placeholders, numbers, markup, line breaks, length limits, and exact glossary terminology.
- A provider-neutral Japanese LLM evaluation contract with context-aware prompts, strict JSON parsing, and explicit protocol diagnostics.
- One shared `Issue` model for Rule and LLM findings.
- A transparent Hybrid policy: Rule-addressable types come from rules; LLM-required types come from the context-aware LLM.
- Detection evaluation with overall and scoped Precision/Recall/F1, per-type metrics, FP/FN, duplicate, unknown-type, clean-sample, and multi-issue analysis.
- Separate 48-item Development and 60-item Held-out Test splits with freeze and leakage controls.
- An optional local Streamlit demo with Rule Only and Hybrid QA modes, implemented as a presentation layer over the frozen v1 APIs.

## Experiments

The v1 research path compared Rule Only, LLM without context, LLM with context, Prompt revisions, and Hybrid systems. Prompt v2 was rejected after Development regression; the smaller v2.1 revision passed the pre-registered candidate gates.

The first and final Held-out evaluation compared five pre-registered methods. The selected Hybrid Prompt v2.1 result was `TP=58`, `FP=41`, `FN=8`, `Precision=0.5859`, `Recall=0.8788`, and `F1=0.7030` on 60 original synthetic samples with 66 reference detections.

## Known Limitations

- Synthetic, small-scale benchmark only; no claim of production accuracy.
- No professional dual annotation, adjudication, or IAA.
- High LLM false-positive rate, including an 80% clean/hard-negative sample false-alarm rate for the selected Hybrid.
- Severity and span localization are not evaluated.
- No production deployment or real-game-data validation.
- The v1 Held-out Test is frozen and retired from future system tuning.

## Future Work

The next technical priority is a human-reviewed external benchmark and false-positive calibration on new development data. Severity/span evaluation, second-model comparison, stability analysis, and real workflow validation follow after that. Agent or RAG complexity is not a v1 priority.
