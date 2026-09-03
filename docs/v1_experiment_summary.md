# J-GameLQA v1 Development Experiment Summary

## Status

J-GameLQA v1 development experiment was frozen on 2026-09-03. The results in this document are historical results from the 48-item synthetic Development Set with 51 reference detections. They must not be interpreted as held-out Test performance or production accuracy.

Artifact and contract hashes are recorded in `outputs/v1_experiment_freeze_manifest.json`.

## Experiment Conditions

- Detection key: `(string_id, issue_type)`
- Model: `qwen3.5:9b`, local Ollama
- Prompt: shared zero-shot Prompt v1
- Taxonomy: 15 Rule-addressable + 7 LLM-required types
- Temperature: 0
- Thinking: false
- Streaming: false
- Structured output: false
- Retry / repair: off
- Parser: Stage 6A strict parser
- LLM context experiment: identical conditions except Context OFF versus ON
- Hybrid policy: all Rule predictions plus With Context LLM predictions filtered to LLM-required types

## Four-method Results

| Method | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| Rule Only | 26 | 2 | 25 | 0.9286 | 0.5098 | 0.6582 |
| LLM Only — Without Context | 25 | 17 | 26 | 0.5952 | 0.4902 | 0.5376 |
| LLM Only — With Context | 34 | 18 | 17 | 0.6538 | 0.6667 | 0.6602 |
| Rule + Context-aware LLM Hybrid | 49 | 17 | 2 | 0.7424 | 0.9608 | 0.8376 |

All values above are read from the frozen v1 development artifacts.

## Context Result

Adding the six context fields increased LLM-required F1 from 0.4906 to 0.7302. On the analysis-only subset containing keigo, first-person, and character-voice issues, F1 increased from 0.2857 to 0.9167. Context fixed important misses but also introduced new false positives, so the result is descriptive evidence on this small synthetic Development Set rather than a general production claim.

## Hybrid Result

Hybrid retained Rule Only performance on Rule-addressable types: TP 26, FP 2, FN 0, F1 0.9630. It retained With Context LLM performance on LLM-required types: TP 23, FP 15, FN 2, F1 0.7302. The combined Overall F1 was 0.8376.

The two components were complementary: Rule fixed 15 deterministic issues missed by the LLM, while the LLM fixed 23 semantic or pragmatic issues missed by Rule Only.

## Main Bad Cases

- Rule false positives: `DEV_015 / number_extra` and `DEV_017 / terminology_forbidden`.
- Hybrid false positives: 17 total; 2 originated from Rule and 15 from the LLM component.
- Remaining false negatives: `DEV_007 / translationese` and `DEV_034 / translationese`.
- The largest LLM error cluster was `mistranslation` overprediction and confusion between mistranslation and translationese.
- One duplicate LLM detection remained: `DEV_012 / omission`.

## Limitations

- The Development Set is small, synthetic, and repeatedly inspected during system development.
- It has no formal multi-annotator agreement measurement.
- Severity and span are retained but not scored.
- Results come from one frozen model run per context condition.
- Temperature 0 does not guarantee absolute model determinism.
- Development metrics cannot be used as evidence of held-out generalization.

## Held-out Policy

`data/test.csv` and `data/test_annotations.csv` form a separate frozen synthetic held-out Test Set. It must not be used for Prompt tuning, few-shot selection, Rule special cases, or iterative score inspection. No Test inference or Test metrics were produced during Stage 7A.
