# Public Release Audit

Audit date: 2026-09-04
Scope: repository files outside `.git/`, `.venv/`, Python caches, and generated egg-info.

本报告只记录命中位置和处理决定，不复制任何疑似 secret 内容。

## Summary

| Check | Result | Action |
|---|---|---|
| API keys / tokens / passwords / credentials | No credential-shaped value detected | No action |
| Private key headers / common cloud token formats | Not detected | No action |
| Email addresses / phone numbers | Not detected | No action |
| Unnecessary personal information | Not detected | No action |
| Local username | Not detected in release candidate files | No action |
| Absolute Windows paths in public Markdown | One path detected and replaced with `<project-root>` | Resolved |
| Absolute Windows paths in frozen artifacts | Present in 8 historical experiment JSON files | Preserved; see exception below |
| Universal local endpoint | `http://127.0.0.1:11434` | Retained as documented Ollama default |
| Files >= 1 MiB | None | No action |
| LICENSE | Missing | User decision remains pending |

## README Readability

The first 27 lines answer all five release questions without requiring the installation or experiment-history sections:

- What J-GameLQA is
- What game localization QA problem it addresses
- Why Rule Checkers and a Context-aware LLM are separated
- The Hybrid v2.1 Held-out headline result
- The synthetic-benchmark / non-production disclaimer

## Cross-document Metric Consistency

`README.md`, `RELEASE_NOTES.md`, the portfolio one-pager, resume versions, job talk tracks, interview deep-dive, and Held-out result document consistently use 60 Test samples, 66 reference detections, and Hybrid v2.1 `TP=58 / FP=41 / FN=8 / P=0.5859 / R=0.8788 / F1=0.7030`.

The context-sensitive `0.2857 → 0.9167` result is explicitly identified as a Development experiment. DEV Hybrid `F1=0.8522` and Held-out Hybrid `F1=0.7030` are separated by split labels wherever compared.

## Resume Truthfulness

The resume and talk-track files do not claim user scale, customer adoption, production deployment, saved labor hours, business cost reduction, commercial feedback, or production accuracy. The general resume version remains one project heading, one technology line, and four evidence-based bullets.

## Frozen Artifact Exception

Eight historical experiment configuration/comparison JSON files contain machine-specific absolute paths captured at run time. These files are protected by the held-out/development experiment freeze or serve as historical traces. Editing them would invalidate hashes, so they remain unchanged. Public documentation uses relative paths or `<project-root>` and explains that historical artifacts may retain original run metadata.

## Large Files

No repository candidate file exceeds 1 MiB. The largest file is a Held-out bad-case JSON at 116,564 bytes. The six raw JSONL traces total 359,906 bytes; each is between 48,190 and 76,284 bytes.

## Raw Experiment Traces

Raw traces are retained because they are small, use original synthetic data, and support audit of strict parsing and model behavior. They were checked for common credential patterns. Held-out raw traces are frozen historical records and must not be regenerated for tuning.

## Ignored Files

`.gitignore` excludes `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `*.egg-info/`, coverage output, local `.env*`, editor/OS noise, ad-hoc output subdirectories, and regenerable XLSX reports. Formal JSON, CSV, and JSONL experiment artifacts remain public candidates.

## Tracked Candidate Files

The Stage 8C public candidate contains 179 files across project metadata, `src/`, `tests/`, `data/`, `docs/`, `examples/`, and formal `outputs/`. Before the first commit, every candidate is staged and rescanned; ignored local environments, caches, egg-info, IDE/OS files, and the regenerable XLSX report remain outside the index.

## Audit Limitations

Pattern scanning reduces obvious release risk but cannot mathematically prove that every sentence is non-sensitive. Repository visibility, final name, LICENSE, remote creation, GitHub metadata, and first push therefore remain explicit user decisions.
