# Reproducibility

## Scope

本页区分两件事：可安全复现的代码/DEV 演示，以及已经封存、不得再用于调优的 v1 Held-out 结果。默认命令不会调用模型，也不会覆盖正式 artifacts。

## Environment

| Item | v1 environment |
|---|---|
| OS | Windows |
| Python used for release checks | 3.14.7 |
| Package requirement | Python >= 3.11 |
| pandas | 3.0.5 |
| openpyxl | 3.1.5 |
| LLM provider used in frozen experiments | Local Ollama HTTP API |
| Model | `qwen3.5:9b` |

The core project has only two required runtime Python dependencies in `pyproject.toml`: `pandas>=2.3` and `openpyxl>=3.1`. The optional local presentation layer adds `streamlit>=1.63,<2` through the `demo` extra. Ollama and its model are external local runtime components, not Python dependencies. The exact Ollama executable version was not recorded in the frozen config, so this document does not invent one.

## Safe Setup and Verification

```powershell
cd <project-root>
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -X utf8 -m unittest discover -s tests
python -m pip check
python -X utf8 examples\run_rule_demo.py
```

The demo reads only `examples/example_input.csv` and `examples/example_glossary.csv`, writes no report, and makes no provider call.

For the optional manual-input Streamlit demo, install and run:

```powershell
python -m pip install -e ".[demo]"
j-gamelqa-demo
```

Rule Only remains available without Ollama. Hybrid QA uses the frozen Prompt v2.1 and provider settings described below; see `docs/local_demo.md` for the full boundary.

## Frozen LLM Configuration

Both final Held-out LLM candidates used the same settings except Prompt version:

```text
Dataset       60-item Test Set
Model         qwen3.5:9b
Provider      local Ollama
Mode          WITH_CONTEXT
Temperature   0
Thinking      false
Streaming     false
Retry         off
Repair        off
Structured    off
Parser        Stage 6A strict parser
Timeout       120 seconds
```

The final candidate uses Prompt v2.1. Full settings are preserved in `outputs/test_qwen35_prompt_v21_config.json`.

## Dataset and Evaluation Contract

- `data/dev.csv` + `data/dev_annotations.csv`: 48-sample Development Set for iteration.
- `data/test.csv` + `data/test_annotations.csv`: 60-sample, 66-reference Held-out Test, now frozen and retired.
- Input and annotations are stored separately.
- Matching key: `(string_id, issue_type)`.
- Severity and spans are retained but not evaluated in v1.
- Prediction artifacts were frozen before annotations were loaded for final scoring.

## Frozen Hashes

| Artifact | SHA-256 |
|---|---|
| `data/test.csv` | `2EB9565F7334DEB6EC552578ECDB7F7A697DA097F08DBED14F12BAFCCED2E785` |
| `data/test_annotations.csv` | `0C92B3E65779E3DAE06B0E1D9569CFCFC494BEA10A4DE1CBB22837F303E9821B` |
| Prompt v1 / With Context | `11635FC05B3ED316F65978C4575C049787498E453094369937D8FF2E7B5CD906` |
| Prompt v2.1 / With Context | `F17B7336A7DF4048D0A32AD4EF600F6391F85C77F00D0CA5D676A63899F14F69` |
| Held-out protocol | `39E01B0C1507A55D34CDAFB1F4E0421B5654FDCBC96BBD6045D192CF11BC06A2` |
| Held-out comparison JSON | `31208B6B2BF2B3AC1CFDFD3DA14ABC8A76F85EED43A4D1B5AB5FC602F5A8D329` |

`outputs/heldout_evaluation_freeze_manifest.json` records all frozen Rule/Prompt/taxonomy/hybrid source hashes and 22 result artifact hashes. `outputs/v1_release_manifest.json` adds release-document hashes without replacing that experiment freeze.

## Artifact Structure

| Pattern | Meaning |
|---|---|
| `*_config.json` | Frozen runtime configuration |
| `*_raw.jsonl` | One retained raw provider response per input |
| `*_predictions.json` | Parsed unified Issue predictions |
| `*_evaluation.json` | Metrics and diagnostics |
| `*_bad_cases.json` | FP/FN analysis views |
| `*comparison*.json/csv` | Method or ablation comparison |
| `*freeze_manifest.json` | Hashes and no-retuning policy |

Raw JSONL traces are small enough to remain with the release. They may contain model judgments from synthetic inputs, but no API token or credential.

## What May Be Reproduced

- Unit tests and schema validation.
- The Rule demo under `examples/`.
- Development experiments for learning, provided new results do not overwrite frozen artifacts.
- Prompt snapshot hashes from the real builders.

## What Must Not Be Used for Tuning

The v1 Held-out evaluation is historical evidence, not a reusable feedback loop. Do not rerun it after changing Prompt, Rule, taxonomy, model settings, or Hybrid policy and then claim the best score. Future model work requires a new Development v2 and Test v2, or an external human-reviewed evaluation set.
