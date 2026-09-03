# First and Final Held-out Evaluation v1

## Protocol and dataset

This is the first and final evaluation on the 60-item original synthetic held-out Test Set with 66 reference detections. The protocol was frozen before Test inference with SHA-256 `39E01B0C1507A55D34CDAFB1F4E0421B5654FDCBC96BBD6045D192CF11BC06A2`.

The workflow generated and hashed Rule, Prompt v1, and Prompt v2.1 predictions before loading `test_annotations.csv`. Both LLM candidates used Qwen3.5-9B, With Context, temperature 0, thinking off, streaming off, strict parsing, and no retry, repair, or structured output. The only candidate variable was the Prompt.

These results must not be interpreted as production accuracy. This Test Set is now closed to further system tuning.

## Five-method result

| Method | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| Rule Only | 33 | 4 | 33 | 0.8919 | 0.5000 | 0.6408 |
| LLM Prompt v1 | 34 | 42 | 32 | 0.4474 | 0.5152 | 0.4789 |
| LLM Prompt v2.1 | 37 | 40 | 29 | 0.4805 | 0.5606 | 0.5175 |
| Hybrid Prompt v1 | 55 | 43 | 11 | 0.5612 | 0.8333 | 0.6707 |
| Hybrid Prompt v2.1 | 58 | 41 | 8 | 0.5859 | 0.8788 | 0.7030 |

Hybrid v2.1 has a descriptive F1 advantage of `0.0323` over Hybrid v1. This exceeds the pre-registered `< 0.02` broadly-comparable band, but no statistical significance is claimed.

## Development-to-held-out gap

| Method | DEV F1 | Test F1 | Test - DEV |
|---|---:|---:|---:|
| Rule Only | 0.6582 | 0.6408 | -0.0175 |
| LLM Prompt v1 | 0.6602 | 0.4789 | -0.1813 |
| LLM Prompt v2.1 | 0.6733 | 0.5175 | -0.1558 |
| Hybrid Prompt v1 | 0.8376 | 0.6707 | -0.1669 |
| Hybrid Prompt v2.1 | 0.8522 | 0.7030 | -0.1491 |

All five methods decline on Test. The Rule gap is small, while both LLM and Hybrid gaps are large. These are observed development-to-held-out performance gaps on small synthetic sets, not by themselves proof of overfitting.

## Scope comparison

Rule-addressable performance is identical for Rule Only and both Hybrids: TP 33, FP 4, FN 1, Precision 0.8919, Recall 0.9706, F1 0.9296. The four Rule false positives are `TEST_003/number_extra`, `TEST_010/number_mismatch`, `TEST_022/number_extra`, and `TEST_049/markup_modified`; the Rule false negative is `TEST_049/markup_malformed`. These include ordinal/full-width-number hard negatives and a malformed closing tag misclassified as modified. They are recorded without fixing or rerunning Rule.

| LLM-required scope | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| Prompt v1 | 22 | 39 | 10 | 0.3607 | 0.6875 | 0.4731 |
| Prompt v2.1 | 25 | 37 | 7 | 0.4032 | 0.7813 | 0.5319 |

| Context-sensitive scope | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| Prompt/Hybrid v1 | 11 | 7 | 3 | 0.6111 | 0.7857 | 0.6875 |
| Prompt/Hybrid v2.1 | 13 | 8 | 1 | 0.6190 | 0.9286 | 0.7429 |

## Focus issue types

| Type | Prompt | Pred | TP | FP | FN | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| mistranslation | v1 | 21 | 4 | 17 | 1 | 0.1905 | 0.8000 | 0.3077 |
| mistranslation | v2.1 | 15 | 4 | 11 | 1 | 0.2667 | 0.8000 | 0.4000 |
| translationese | v1 | 3 | 3 | 0 | 2 | 1.0000 | 0.6000 | 0.7500 |
| translationese | v2.1 | 3 | 2 | 1 | 3 | 0.6667 | 0.4000 | 0.5000 |
| keigo_mismatch | v1 | 6 | 4 | 2 | 1 | 0.6667 | 0.8000 | 0.7273 |
| keigo_mismatch | v2.1 | 9 | 4 | 5 | 1 | 0.4444 | 0.8000 | 0.5714 |
| first_person_mismatch | v1 | 5 | 4 | 1 | 0 | 0.8000 | 1.0000 | 0.8889 |
| first_person_mismatch | v2.1 | 5 | 4 | 1 | 0 | 0.8000 | 1.0000 | 0.8889 |
| character_voice_mismatch | v1 | 7 | 3 | 4 | 2 | 0.4286 | 0.6000 | 0.5000 |
| character_voice_mismatch | v2.1 | 7 | 5 | 2 | 0 | 0.7143 | 1.0000 | 0.8333 |

The DEV mistranslation FP reduction generalizes directionally: Test FP falls from 17 to 11 with unchanged TP/Recall, although overprediction remains severe. The DEV translationese gain does not generalize: Test recall falls from 0.60 to 0.40. Keigo also regresses through three additional false positives, while character voice is the largest positive change.

Omission remains the dominant error source: Prompt v1 has TP/FP/FN `3/13/1`; Prompt v2.1 has `4/15/0`. Addition improves from `1/2/3` to `2/2/2`.

## Clean hard negatives

| Method | False-alarmed clean samples | Rate |
|---|---:|---:|
| Rule Only | 2/10 | 0.20 |
| LLM Prompt v1 | 5/10 | 0.50 |
| LLM Prompt v2.1 | 7/10 | 0.70 |
| Hybrid Prompt v1 | 6/10 | 0.60 |
| Hybrid Prompt v2.1 | 8/10 | 0.80 |

Prompt v2.1's better issue-level aggregate comes with worse sample-level false alarms on legitimate context-heavy translations. Examples include treating a teacher's request to drop formalities as a keigo violation (`TEST_002`) and rejecting valid system localization (`TEST_008`).

## Multi-issue samples

| Method | Fully detected | Partially detected | Completely missed |
|---|---:|---:|---:|
| Rule Only | 0 | 13 | 3 |
| LLM Prompt v1 | 2 | 12 | 2 |
| LLM Prompt v2.1 | 3 | 12 | 1 |
| Hybrid Prompt v1 | 8 | 8 | 0 |
| Hybrid Prompt v2.1 | 11 | 5 | 0 |

Hybrid v2.1 fully detects three more multi-issue samples than Hybrid v1. Neither Hybrid completely misses a multi-issue sample, but partial detection remains common.

## Protocol reliability

Both prompts complete 60/60 provider and protocol successes with zero parse, schema, validation, or unknown-type failures. Prompt v1 has three duplicate detection keys and Prompt v2.1 has two. Mean latency is 2.5006 seconds for v1 and 2.1007 seconds for v2.1. No provider failure or retry occurred.

## Remaining Hybrid v2.1 bad cases

Hybrid v2.1 retains 41 false positives. The largest categories are omission 15, mistranslation 11, keigo 5, addition 2, character voice 2, and Rule number false positives 3. It has eight false negatives:

- `TEST_033/addition`
- `TEST_034/addition`
- `TEST_037/translationese`
- `TEST_048/translationese`
- `TEST_049/markup_malformed`
- `TEST_055/keigo_mismatch`
- `TEST_058/mistranslation`
- `TEST_060/translationese`

These failures are frozen observations, not inputs to another tuning cycle.

## Conclusion

Prompt v2.1's aggregate DEV improvement shows evidence of generalization on this held-out set: it improves LLM-required and Hybrid Precision, Recall, and F1 relative to Prompt v1. Hybrid v2.1 is the selected descriptive winner under the pre-registered policy. However, both candidates show large DEV-to-Test gaps, absolute Precision remains low, translationese/keigo regress, and clean false-alarm performance is poor. The result supports a final prototype choice, not a production-readiness claim.
