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
- [x] `origin` points to `https://github.com/liguozheng-ac/j-gamelqa.git`
- [x] Working tree is clean after the public release push

## Publication status

- [x] Add MIT License
- [x] Confirm Public repository visibility
- [x] Confirm repository name `j-gamelqa`
- [x] Create the empty GitHub repository
- [x] Configure GitHub remote
- [x] Perform the first push to `main`
- [x] Confirm the GitHub description
- [x] Verify the online README, MIT License, documentation links, and SVG assets
- [x] Verify Local Demo installation and startup instructions are visible online
- [x] Complete the post-push secret, privacy, absolute-path, and ignored-file audit
- [ ] Add the suggested GitHub topics manually (the available GitHub integration has no repository-topics write interface)

## LICENSE decision

The user selected the standard MIT License. The repository-root `LICENSE` file carries `Copyright (c) 2026 Guozheng Li` without additional restrictions.

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
