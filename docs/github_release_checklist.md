# GitHub Release Checklist

## Automated / Codex-verified

- [x] README first screen explains project, problem, Rule + LLM, and key Held-out result
- [x] No credential-shaped secrets detected by repository pattern scan
- [x] No email address, phone number, or unnecessary personal profile detected
- [x] No local absolute Windows path remains in public Markdown
- [x] Historical absolute paths are limited to preserved experiment artifacts and documented
- [x] `.venv/`, caches, `*.pyc`, `.pytest_cache/`, and `*.egg-info/` are ignored
- [x] Formal JSON/CSV/JSONL experiment artifacts remain candidate files
- [x] Unit tests pass
- [x] `pip check` passes
- [x] Rule demo runs without Ollama
- [x] Frozen hashes pass
- [x] Local branch renamed to `main`
- [x] Public candidate file inventory reviewed
- [x] Staged files reviewed and rescanned before the initial commit
- [x] Initial local release commit created
- [x] Remote is not configured
- [x] Working tree is clean after the local release commit

## User decisions before publication

- [ ] Decide and add an appropriate LICENSE, or explicitly publish without one
- [ ] Confirm Public repository visibility (recommended for this portfolio project)
- [ ] Confirm repository name `j-gamelqa`
- [ ] Configure GitHub remote
- [ ] Perform the first push
- [ ] Apply or edit the proposed GitHub description and topics

## LICENSE decision

Codex has deliberately not selected a license. The user should choose between:

1. A permissive open-source license that allows use, modification, and redistribution while retaining the copyright and license notice.
2. Publicly readable source with no added license, which by default does not grant others permission to copy, modify, or redistribute it.

## Suggested GitHub About

**English description**

> Hybrid rule-based and context-aware LLM evaluation system for Chinese-to-Japanese game localization QA.

**中文备用**

> 面向中译日游戏本地化的规则质检、上下文感知大模型评测与混合 QA 系统。

**Suggested topics**

```text
japanese
game-localization
localization-qa
llm-evaluation
qwen
ollama
python
nlp
prompt-engineering
```
