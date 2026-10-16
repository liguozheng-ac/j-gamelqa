# J-GameLQA

**English** | [简体中文](README.zh-CN.md)

**Japanese Game Localization QA & LLM Evaluation System**

A hybrid quality assurance system for Chinese-to-Japanese game localization, combining deterministic rule checks with context-aware LLM evaluation.

J-GameLQA reviews Chinese source text, Japanese translations, and game context to identify issues for human review. A reproducible offline evaluation compares rule-based, LLM, and hybrid approaches.

## Problem

Game localization QA involves two different kinds of checks:

- **Technical checks:** placeholders, numbers, markup, line breaks, length limits, and terminology benefit from deterministic rules with explicit evidence.
- **Language and character checks:** mistranslation, omission, translationese, keigo, first-person choice, and character voice require semantic understanding and game context.

J-GameLQA assigns each issue type to the appropriate QA layer and represents findings with a shared `Issue` data structure.

## Core Idea

![J-GameLQA architecture](docs/assets/j-gamelqa-architecture.svg)

The frozen v1 candidate combines **Rule Baseline v1 + Qwen3.5-9B + Prompt v2.1 + With Context**. Hybrid routing uses rule outputs for rule-addressable types and context-aware LLM outputs for LLM-required types, rather than voting between the two systems.

> **Key held-out result**<br>
> 60 synthetic samples · 66 reference detections<br>
> Hybrid v2.1 — Precision `0.5859` · Recall `0.8788` · F1 `0.7030`<br>
> *Synthetic held-out benchmark; not production accuracy.*

## Local Demo

The optional Streamlit interface accepts Chinese source text, a Japanese translation, and character context. It displays Rule, LLM, and Hybrid issues separately, using the existing QA modules without loading the development or test benchmarks.

```powershell
python -m pip install -e ".[demo]"
ollama pull qwen3.5:9b
j-gamelqa-demo
```

**Rule Only** works without Ollama. **Hybrid QA** requires a running local Ollama service and the `qwen3.5:9b` model. See [Local Demo](docs/local_demo.md) for requirements, modes, and error handling.

## Architecture

| Layer | Components | Responsibility |
|---|---|---|
| Data | Development set, held-out test set, glossary, reference annotations | Separate system inputs from reference answers and control answer leakage |
| Rule | Placeholder, Number, Markup, Line Break, Length, Terminology | Detect deterministic technical issues with explicit evidence |
| LLM | Prompt contract, game context, strict JSON parser, protocol diagnostics | Assess meaning, naturalness, and character relationships while preserving raw responses |
| Evaluation | Overall, rule-addressable, LLM-required, context-sensitive, bad cases | Match detections by `(string_id, issue_type)` and analyze false positives and false negatives |

See [Architecture](docs/architecture.md) for module boundaries and [Experiment Flow](docs/experiment_flow.md) for the research process.

## Evaluation Design

- **Development Set:** 48 original synthetic samples with 51 reference detections, used for prompt and system development.
- **Held-out Test Set:** 60 independent original synthetic samples with 66 reference detections, opened once for final evaluation and now permanently frozen.
- **Taxonomy:** 15 rule-addressable issue types and 7 LLM-required issue types.
- **Detection key:** `(string_id, issue_type)`. Severity and spans are retained in v1 but excluded from detection matching.
- **Diagnostics:** false positives, false negatives, duplicate predictions, unknown issue types, and parse/schema/validation failures.

## Held-out Results

The first and final evaluation on the **60-item original synthetic held-out test set (66 reference detections)** produced:

| Method | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| Rule Only | 33 | 4 | 33 | 0.8919 | 0.5000 | 0.6408 |
| LLM Prompt v1 | 34 | 42 | 32 | 0.4474 | 0.5152 | 0.4789 |
| LLM Prompt v2.1 | 37 | 40 | 29 | 0.4805 | 0.5606 | 0.5175 |
| Hybrid Prompt v1 | 55 | 43 | 11 | 0.5612 | 0.8333 | 0.6707 |
| **Hybrid Prompt v2.1** | **58** | **41** | **8** | **0.5859** | **0.8788** | **0.7030** |

`F1 = 0.7030` measures issue detection on a small synthetic benchmark; it is not production accuracy. See [Held-out Evaluation Results](docs/heldout_evaluation_results.md) for the protocol, detailed metrics, and bad cases.

## Why Context Matters

In a controlled development experiment, the model, Prompt v1, sampling settings, and parser remained fixed. The only input change was adding `speaker`, `addressee`, `scene`, `relationship`, `context_before`, and `context_after`:

```text
Context-sensitive F1: 0.2857 → 0.9167
```

This analysis subset covers `keigo_mismatch`, `first_person_mismatch`, and `character_voice_mismatch`. The improvement supports the value of context for pragmatic judgments on the development set; it is not a held-out or production result.

## Prompt Optimization Story

```text
Prompt v1
  ↓  bad-case analysis: mistranslation overprediction
Prompt v2
  ↓  added too many rules; errors shifted toward keigo and primary metrics regressed
Prompt v2.1
  ↓  minimal boundary guidance; passed pre-registered DEV candidate gates
Held-out
  Hybrid v1 F1 0.6707 → Hybrid v2.1 F1 0.7030
```

Prompt v2 is preserved as a negative experiment. The held-out advantage of v2.1 is descriptive evidence; no statistical significance is claimed. See [Prompt v2 Results](docs/prompt_v2_development_results.md) and [Prompt v2.1 Results](docs/prompt_v21_development_results.md).

## Important Limitations

> **J-GameLQA is a QA assistant for human review.** The available evaluation evidence comes from original synthetic benchmarks.

- The datasets are small and contain no real commercial game text.
- Reference annotations have not undergone professional dual annotation, adjudication, or inter-annotator agreement (IAA) assessment.
- LLM false positives remain a major limitation: Hybrid v2.1 raised at least one false alarm on **8 of 10** clean / hard-negative held-out samples.
- Severity and spans are retained as fields but have not been formally evaluated.
- Production deployment, throughput, cost, privacy controls, and human review workflows have not been validated.
- The 60-item held-out test set is **frozen and retired**. It must not be reused to tune prompts, rules, or routing policy.

## Quickstart

Windows PowerShell, using Python 3.14:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -X utf8 -m unittest discover -s tests
python -X utf8 examples\run_rule_demo.py
```

The last command runs the rule pipeline on new synthetic demo data. It does not call Ollama, read reference annotations, or overwrite formal experiment artifacts. To inspect the available CLIs:

```powershell
j-gamelqa-rules --help
j-gamelqa-evaluate --help
j-gamelqa-llm-evaluate --help
```

The default quickstart excludes held-out rerun commands because the evaluation is sealed. See [Reproducibility](docs/reproducibility.md) for the environment and experiment settings.

## Repository Structure

```text
j-gamelqa/
├── data/                   # DEV/Test inputs, reference annotations, glossary
├── examples/               # New synthetic rule demo without reference answers
├── docs/                   # Architecture, experiments, prompts, portfolio materials
├── src/j_gamelqa/
│   ├── rules/              # Six deterministic checker categories
│   ├── providers/          # Injectable local Ollama provider
│   ├── demo_*.py           # Optional Streamlit UI and single-record adapter
│   ├── models.py           # Unified Issue contract
│   ├── llm_evaluator.py    # Prompt → strict parser → Issue
│   ├── hybrid.py           # Rule / LLM issue-type routing
│   └── evaluate.py         # Detection metrics and diagnostics
├── tests/                  # Unit tests requiring no real Ollama calls
├── outputs/                # Frozen experiment artifacts and hash manifests
├── README.zh-CN.md         # Chinese README
├── pyproject.toml
└── RELEASE_NOTES.md
```

## Documentation

Detailed documentation currently includes both English and Chinese; the links below retain their original language.

- [Architecture](docs/architecture.md): module boundaries and design decisions
- [Local Demo](docs/local_demo.md): installation, startup, modes, and limitations
- [Experiment Flow](docs/experiment_flow.md): hypotheses, experiments, and decisions from the rule baseline to the final held-out evaluation
- [Portfolio One-pager](docs/portfolio_onepager.md): a one-minute project overview
- [Reproducibility](docs/reproducibility.md): environment, protocols, hashes, and safe reproduction scope
- [Interview Deep-Dive](docs/interview_deep_dive.md): 16 interview questions and three project introductions
- [Job Talk Tracks](docs/job_talk_tracks.md): 30-second and 90-second pitches, with follow-up questions for three job tracks
- [Chinese Resume Versions](docs/resume_cn.md): general and role-specific project descriptions
- [Public Release Audit](docs/public_release_audit.md) and [GitHub Checklist](docs/github_release_checklist.md): publication checks
- [Data Schema](docs/data_schema.md) and [LLM Evaluator](docs/llm_evaluator.md): input fields and evaluation contracts
- [Release Notes](RELEASE_NOTES.md): v1 functionality, results, and known limitations

## Future Work

1. Build an external benchmark reviewed by language professionals, with dual annotation, adjudication, and IAA assessment.
2. Study false-positive control and hard-negative calibration on a new Development v2 set.
3. Add severity and span localization evaluation.
4. Compare a second model and repeated-run stability without reusing the retired test set.
5. Validate human review workflows, cost, and throughput with authorized real localization data.

## License

This project is licensed under the [MIT License](LICENSE).
