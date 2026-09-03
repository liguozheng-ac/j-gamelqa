# Prompt v2 Development Experiment

## Status

Prompt v2 was evaluated exactly once on the frozen 48-item Development Set. The result is preserved even though it did not improve on Prompt v1. No held-out Test inference or Test metric was produced.

## Controlled configuration

- Model: `qwen3.5:9b` through local Ollama
- Input mode: With Context
- Prompt: v2, zero-shot
- Temperature: 0
- Thinking: false
- Streaming: false
- Retry and repair: off
- Structured output: off
- Parser: existing strict parser
- Dataset: 48 DEV records only

Prompt v2 keeps Prompt v1 intact and adds only general taxonomy-boundary and final-consistency guidance. It does not change the 22-type taxonomy or JSON output contract.

## Protocol diagnostics

| Diagnostic | Result |
|---|---:|
| Total requests | 48 |
| Provider successes | 48 |
| Provider failures | 0 |
| Protocol-successful responses | 47 |
| Parse failures | 1 |
| Schema failures | 0 |
| Validation failures | 0 |
| Unknown issue types | 0 |
| Duplicate detection keys | 2 |
| Protocol success rate | 0.9792 |

`DEV_016` produced the sole parse failure. The model placed a long internal deliberation inside `evidence` and emitted invalid JSON quoting. No retry or repair was attempted. Duplicate keys were `DEV_012 / omission` and `DEV_043 / mistranslation`; detection scoring deduplicates keys while retaining diagnostics.

## Prompt v1 versus Prompt v2

| Scope | Version | TP | FP | FN | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|---:|---:|
| Overall | Prompt v1 | 34 | 18 | 17 | 0.6538 | 0.6667 | 0.6602 |
| Overall | Prompt v2 | 32 | 17 | 19 | 0.6531 | 0.6275 | 0.6400 |
| LLM-required | Prompt v1 | 23 | 15 | 2 | 0.6053 | 0.9200 | 0.7302 |
| LLM-required | Prompt v2 | 21 | 16 | 4 | 0.5676 | 0.8400 | 0.6774 |
| Context-sensitive | Prompt v1 | 11 | 2 | 0 | 0.8462 | 1.0000 | 0.9167 |
| Context-sensitive | Prompt v2 | 10 | 5 | 1 | 0.6667 | 0.9091 | 0.7692 |

Prompt v2 therefore did not meet the design objective. It reduced one net Overall FP but also lost two TP. In the primary LLM-required scope it added one net FP and lost two TP.

## Focus issue types

| Type | References | v1 predictions | v1 TP/FP/FN | v1 F1 | v2 predictions | v2 TP/FP/FN | v2 F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| mistranslation | 4 | 11 | 4/7/0 | 0.5333 | 9 | 4/5/0 | 0.6154 |
| translationese | 3 | 1 | 1/0/2 | 0.5000 | 1 | 1/0/2 | 0.5000 |
| omission | 4 | 8 | 4/4/0 | 0.6667 | 7 | 3/4/1 | 0.5455 |
| addition | 3 | 5 | 3/2/0 | 0.7500 | 5 | 3/2/0 | 0.7500 |
| keigo_mismatch | 4 | 5 | 4/1/0 | 0.8889 | 7 | 3/4/1 | 0.5455 |
| first_person_mismatch | 3 | 3 | 3/0/0 | 1.0000 | 3 | 3/0/0 | 1.0000 |
| character_voice_mismatch | 4 | 5 | 4/1/0 | 0.8889 | 5 | 4/1/0 | 0.8889 |

The mistranslation boundary improved: two fewer false positives, with all four references retained. `DEV_034` changed from a false-positive `mistranslation` to the correct `translationese`. However, `translationese` aggregate recall stayed at 0.3333 because the gain on `DEV_034` was offset by losing `DEV_041`, while `DEV_007` remained missed.

The context guardrail regressed. New `keigo_mismatch` false positives appeared on `DEV_006`, `DEV_037`, and `DEV_041`, and the true `DEV_040 / keigo_mismatch` became a false negative. The instruction that context is evidence rather than proof was therefore not sufficient for this model/run.

## Paired changes

- Resolved false positives: 6 (`DEV_006/omission`, `DEV_016/length_overflow`, `DEV_023/omission`, `DEV_034/mistranslation`, `DEV_037/mistranslation`, `DEV_043/number_mismatch`).
- New false positives: 5 (`DEV_002/omission`, `DEV_006/keigo_mismatch`, `DEV_037/keigo_mismatch`, `DEV_041/keigo_mismatch`, `DEV_044/omission`).
- FN to TP: 1 (`DEV_034/translationese`).
- TP to FN: 3 (`DEV_040/keigo_mismatch`, `DEV_041/translationese`, `DEV_043/omission`).
- Type changes: `DEV_006 omission → keigo_mismatch`; `DEV_034 mistranslation → translationese`; `DEV_037 mistranslation → keigo_mismatch`; `DEV_041 translationese → keigo_mismatch`.

No paired change from `mistranslation` to `character_voice_mismatch`, or the reverse, occurred in this run.

These key-level counts need careful interpretation. `DEV_016 / length_overflow` disappeared because that record failed parsing, so it is not evidence of a better judgment. `DEV_006` and `DEV_037` merely exchanged one false-positive label for another, while `DEV_041` changed from a true `translationese` detection to a false `keigo_mismatch`. Of the listed boundary changes, `DEV_034 mistranslation → translationese` is the clear intended improvement.

## Hybrid impact

The Hybrid policy and frozen Rule predictions were reused unchanged. Only the LLM component changed from Prompt v1 to Prompt v2.

| Version | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| Hybrid v1 | 49 | 17 | 2 | 0.7424 | 0.9608 | 0.8376 |
| Hybrid + Prompt v2 | 47 | 18 | 4 | 0.7231 | 0.9216 | 0.8103 |
| Delta | -2 | +1 | +2 | -0.0193 | -0.0392 | -0.0273 |

Rule-addressable Hybrid metrics remained byte-for-byte equivalent in value: TP 26, FP 2, FN 0, F1 0.9630. The regression came entirely from the Prompt v2 LLM-required component.

## Interpretation and limitations

This is a small synthetic Development Set and a single deterministic-looking local run, not production evidence. Temperature 0 does not guarantee identical hardware/runtime output. Detection scoring ignores severity and spans. One parse failure materially affected one item, and no repair was allowed by the experiment contract. The Test Set remains sealed, so there is deliberately no claim about held-out generalization.

Prompt v2 should not replace Prompt v1 as the preferred candidate based on this Development result. Any v2.1 hypothesis should be designed as a new version and must not overwrite this experiment.
