# Git Commit Plan

Stage 8B 不执行 commit。用户人工审阅后，建议首次提交信息：

```text
Initial public release: J-GameLQA v1.0.0
```

建议提交范围：

- 项目 metadata：README、Release Notes、`pyproject.toml`、`.gitignore`
- 原创 synthetic data、glossary 与 benchmark manifests
- Rule、LLM contract、Hybrid 和 Evaluation 源码
- unittest
- 冻结的正式 experiment artifacts 与 raw traces
- 架构图、实验流程图和技术文档
- Demo examples

提交前仍需人工决定 LICENSE，并逐项执行 `docs/github_release_checklist.md`。不要在首个 commit 中包含 `.venv`、cache、egg-info、IDE 文件、个人联系方式或本地 secret。
