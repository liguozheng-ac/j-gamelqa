# Held-out Evaluation Protocol v1

## Status and purpose

This protocol is frozen before the first formal inference on the 60-item synthetic held-out Test Set. Stage 7C is the first and final evaluation on this Test Set. After evaluation, its cases and metrics may be used only to explain the frozen result, not to tune Prompt, Rule, taxonomy, annotations, model settings, or Hybrid policy.

## Fixed methods

Only these five systems enter the formal result table:

1. Rule Only
2. Qwen3.5-9B + Prompt v1 + With Context
3. Qwen3.5-9B + Prompt v2.1 + With Context
4. Hybrid v1: frozen Rule + Prompt v1 LLM
5. Hybrid v2.1: frozen Rule + Prompt v2.1 LLM

Prompt v2, No Context, additional models, new prompts, and modified rules are excluded.

## Frozen inputs and prompts

- `test.csv` SHA-256: `2EB9565F7334DEB6EC552578ECDB7F7A697DA097F08DBED14F12BAFCCED2E785`
- `test_annotations.csv` SHA-256: `0C92B3E65779E3DAE06B0E1D9569CFCFC494BEA10A4DE1CBB22837F303E9821B`
- Prompt v1 Without Context SHA-256: `F36162A11642FF070F1EBCBE4A04AA1B82864FEFCC61AE23117BF0F6A495218A`
- Prompt v1 With Context SHA-256: `11635FC05B3ED316F65978C4575C049787498E453094369937D8FF2E7B5CD906`
- Prompt v2.1 Without Context SHA-256: `AC27E075DB46252EFCB7C1F3453EE3BA67BAF9013C378C462AA26A4E8760E774`
- Prompt v2.1 With Context SHA-256: `F17B7336A7DF4048D0A32AD4EF600F6391F85C77F00D0CA5D676A63899F14F69`

## Fixed generation settings

- Dataset: 60 records from `data/test.csv`
- Model: `qwen3.5:9b`
- Provider: local Ollama
- Input mode: With Context
- Temperature: 0
- Thinking: false
- Streaming: false
- Retry: off
- Repair: off
- Structured output: off
- Parser: existing strict parser
- Timeout: 120 seconds

The only LLM-candidate variable is Prompt v1 versus Prompt v2.1.

## Prediction-before-annotation workflow

1. Verify all frozen hashes and freeze this protocol.
2. Load only `test.csv` and glossary; generate Rule predictions.
3. Load only `test.csv` and glossary; generate all Prompt v1 raw responses and predictions.
4. Load only `test.csv` and glossary; generate all Prompt v2.1 raw responses and predictions.
5. Calculate and freeze SHA-256 for all prediction artifacts.
6. Only after steps 1–5 succeed, load `test_annotations.csv` and calculate metrics.

Generation functions do not accept an annotation path. Parse/schema/model-answer failures are model behavior and are never retried or repaired. A genuine provider/transport failure invalidates that candidate run for final comparison; its attempt artifacts are retained, infrastructure may be fixed, and the entire candidate must use the same frozen settings if rerun.

## Detection and Hybrid policy

- Detection key: `(string_id, issue_type)`
- Severity and spans are retained but not used for matching.
- Rule-addressable predictions come from the frozen Rule Engine.
- LLM-required predictions come from the corresponding Prompt candidate.
- LLM technical predictions do not enter Hybrid.
- Context-sensitive is an analysis-only subset containing `keigo_mismatch`, `first_person_mismatch`, and `character_voice_mismatch`.

## Pre-registered metrics

Primary metric: Overall Detection F1.

Every method also reports TP, FP, FN, Precision, and Recall. Secondary scopes are Rule-addressable, LLM-required, and Context-sensitive. Focus types are mistranslation, translationese, keigo mismatch, first-person mismatch, and character-voice mismatch.

Auxiliary sample-level analyses:

- Clean false-alarm rate: clean Test samples with at least one prediction divided by 10.
- Multi-issue detection: among 16 multi-issue samples, count fully detected, partially detected, and completely missed samples.

These auxiliary measures do not replace issue-level detection metrics.

## Pre-registered comparison and winner policy

The primary candidate comparison is Hybrid v1 versus Hybrid v2.1 Overall F1. Secondary evidence is LLM-required F1, Precision/Recall trade-off, protocol reliability, and paired bad-case patterns.

An absolute Hybrid Test F1 gap below `0.02` is described as broadly comparable on this held-out set; it is not called a significant advantage. No p-values, bootstrap significance, or post-hoc threshold changes are added. Development-to-Test changes are called observed development-to-held-out performance gaps, not automatically overfitting.

## No-retuning rule

After the first Test inference begins, no Prompt, Rule, taxonomy, annotations, Test sample, model setting, parser, special case, or Hybrid policy may change. No Test prediction may be regenerated in response to parse, schema, semantic, or metric results. Future development requires a new Test v2 or an external/human-reviewed evaluation set.
