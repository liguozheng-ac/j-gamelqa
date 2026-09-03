# Prompt v2.1 Final Development Experiment

## Status

Prompt v2.1 was run exactly once on the frozen 48-item Development Set. It is the final Development prompt experiment: no Prompt v2.2/v3 DEV iteration follows. The pre-registered Candidate Gate passed, so Prompt v1 and Prompt v2.1 are the two held-out candidates. Prompt v2 remains a rejected experimental candidate.

No held-out Test inference, metric, or bad-case inspection was performed.

## Minimal design

Prompt v2.1 is built directly on frozen Prompt v1, not Prompt v2. It adds only:

- the `mistranslation` / `translationese` meaning boundary;
- one short no-double-label rule requiring independent evidence;
- one sentence stating that relationship or hierarchy alone cannot prove keigo or voice errors;
- one general evidence-support rule; and
- a short-evidence, JSON-only instruction.

It deliberately removes Prompt v2's extended omission/addition tutorials, specific-type priority hierarchy, technical-versus-semantic hierarchy, and final consistency checklist.

Prompt hashes:

- Without Context: `AC27E075DB46252EFCB7C1F3453EE3BA67BAF9013C378C462AA26A4E8760E774`
- With Context: `F17B7336A7DF4048D0A32AD4EF600F6391F85C77F00D0CA5D676A63899F14F69`

## Pre-registered Candidate Gate

The executable and documented gate was hashed before formal inference. Prompt v2.1 advances only if all conditions pass:

1. LLM-required Precision > 0.6053
2. LLM-required Recall >= 0.8800
3. LLM-required F1 >= 0.7302
4. Hybrid F1 >= 0.8376
5. 48/48 strict-protocol responses and zero provider failures

No threshold was changed after seeing results.

## Controlled configuration and protocol

- Model: `qwen3.5:9b` through local Ollama
- Dataset: 48 DEV records only
- Mode: With Context
- Temperature: 0
- Thinking: false
- Streaming: false
- Retry / repair / structured output: off
- Parser: existing strict parser
- Formal runs: one

| Diagnostic | Result |
|---|---:|
| Total requests | 48 |
| Provider successes | 48 |
| Provider failures | 0 |
| Protocol successes | 48 |
| Parse failures | 0 |
| Schema failures | 0 |
| Validation failures | 0 |
| Unknown issue types | 0 |
| Duplicate detection keys | 1 |
| Protocol success rate | 1.0000 |

The duplicate detection key is `DEV_012 / omission`. Scoring deduplicates the key and preserves the diagnostic.

## Three-version Development comparison

| Prompt | LLM-required P | R | F1 | Hybrid P | R | F1 |
|---|---:|---:|---:|---:|---:|---:|
| v1 | 0.6053 | 0.9200 | 0.7302 | 0.7424 | 0.9608 | 0.8376 |
| v2 | 0.5676 | 0.8400 | 0.6774 | 0.7231 | 0.9216 | 0.8103 |
| v2.1 | 0.6389 | 0.9200 | 0.7541 | 0.7656 | 0.9608 | 0.8522 |

Prompt v2.1 Overall LLM-only is TP 34, FP 16, FN 17, Precision 0.6800, Recall 0.6667, F1 0.6733. LLM-required is TP 23, FP 13, FN 2. Hybrid is TP 49, FP 15, FN 2.

Context-sensitive metrics are:

| Prompt | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| v1 | 11 | 2 | 0 | 0.8462 | 1.0000 | 0.9167 |
| v2 | 10 | 5 | 1 | 0.6667 | 0.9091 | 0.7692 |
| v2.1 | 11 | 4 | 0 | 0.7333 | 1.0000 | 0.8462 |

Thus v2.1 restores context-sensitive recall but still has two more context-sensitive false positives than v1.

## Focus issue types

| Type | Prompt | Pred | TP | FP | FN | P | R | F1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| mistranslation | v1 | 11 | 4 | 7 | 0 | 0.3636 | 1.0000 | 0.5333 |
| mistranslation | v2 | 9 | 4 | 5 | 0 | 0.4444 | 1.0000 | 0.6154 |
| mistranslation | v2.1 | 7 | 4 | 3 | 0 | 0.5714 | 1.0000 | 0.7273 |
| translationese | v1 | 1 | 1 | 0 | 2 | 1.0000 | 0.3333 | 0.5000 |
| translationese | v2 | 1 | 1 | 0 | 2 | 1.0000 | 0.3333 | 0.5000 |
| translationese | v2.1 | 2 | 2 | 0 | 1 | 1.0000 | 0.6667 | 0.8000 |
| keigo_mismatch | v1 | 5 | 4 | 1 | 0 | 0.8000 | 1.0000 | 0.8889 |
| keigo_mismatch | v2 | 7 | 3 | 4 | 1 | 0.4286 | 0.7500 | 0.5455 |
| keigo_mismatch | v2.1 | 6 | 4 | 2 | 0 | 0.6667 | 1.0000 | 0.8000 |
| first_person_mismatch | v1 | 3 | 3 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| first_person_mismatch | v2 | 3 | 3 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| first_person_mismatch | v2.1 | 3 | 3 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| character_voice_mismatch | v1 | 5 | 4 | 1 | 0 | 0.8000 | 1.0000 | 0.8889 |
| character_voice_mismatch | v2 | 5 | 4 | 1 | 0 | 0.8000 | 1.0000 | 0.8889 |
| character_voice_mismatch | v2.1 | 6 | 4 | 2 | 0 | 0.6667 | 1.0000 | 0.8000 |

For the three translationese boundary records: v2.1 correctly detects `DEV_007` and `DEV_034`, but still misses `DEV_041`. It therefore preserves the intended `DEV_034` reclassification and adds `DEV_007`, but does not restore v1's `DEV_041` detection.

For keigo, v2.1 removes the v2 false positives on `DEV_006` and `DEV_007` and restores the true `DEV_040` detection. It still produces false positives on `DEV_037` and `DEV_041`, so it does not regain v1's keigo precision.

## Paired changes from Prompt v1

- Resolved FP keys: 7, of which 6 are LLM-required and one is technical.
- New FP keys: 5, of which 4 are LLM-required and one is technical.
- FN to TP: `DEV_007 / translationese`, `DEV_034 / translationese`.
- TP to FN: `DEV_041 / translationese`, `DEV_043 / omission`.
- Notable relabels: `DEV_007 keigo → translationese`; `DEV_034 mistranslation → translationese`; `DEV_035 mistranslation → character_voice`; `DEV_037 mistranslation → keigo`; `DEV_041 translationese → keigo`.

Some relabels exchange one false-positive type for another, so resolved/new counts must not be read as five independent quality gains.

## Evidence behavior

Prompt v2.1 fixes the v2 protocol regression: `DEV_016` now produces valid JSON with a single-sentence evidence field rather than internal deliberation. It still makes a content error on that record by claiming the 10-character target has 12 characters and reporting `length_overflow`; protocol compliance therefore does not imply QA correctness. Across 51 raw predictions, evidence has no line breaks or embedded double quotation marks. Mean evidence length is 118.96 characters and maximum length is 217, so the shortness instruction improved structure but was not obeyed consistently. No parser change helped the result.

## Candidate decision and limitations

All five pre-registered checks passed. The recorded decision is `prompt_v1_and_prompt_v2.1_are_held_out_candidates`.

This selection is based only on a small synthetic Development Set. It does not establish held-out generalization. Detection matching still ignores severity and spans. Context-sensitive Precision remains below v1, and several semantic false positives remain. The next step is candidate selection/final held-out evaluation, not further DEV prompt editing.
