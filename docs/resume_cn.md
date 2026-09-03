# 中文简历项目经历

以下版本只能择一放入同一份简历，避免重复堆叠。数字均来自冻结 artifact；`F1` 不应改写为“准确率”。

## 通用主版本

### J-GameLQA｜日语游戏本地化智能质检与大模型评测系统

**技术：** Python / pandas / Ollama / Qwen3.5-9B / Prompt Engineering / LLM Evaluation

- 独立设计中文→日语游戏本地化 QA 系统，将 Placeholder、数字、Markup、换行、长度和术语等确定性错误交由 Rule Checker，将误译、漏译、翻译腔、敬语、第一人称和角色语气交由 Context-aware LLM。
- 构建 22 类 LQA taxonomy、48 条 Development Set 与 60 条独立 synthetic Held-out Test，并实现基于 `(string_id, issue_type)` 的 Precision/Recall/F1、per-type、Bad Case 和 Hybrid 对比评测。
- 设计 Without/With Context 受控实验，DEV 角色语用子集 F1 从 0.2857 提升至 0.9167；通过 Prompt v1→v2→v2.1 迭代记录 overprediction、错误迁移和负实验。
- 最终 Hybrid v2.1 在 60 条 Held-out synthetic samples 上取得 P=0.5859、R=0.8788、F1=0.7030；同时识别出 hard-negative false alarm 偏高等限制并冻结 Test，避免继续调参污染。

## AI 数据 / 模型评测岗位版本

### J-GameLQA｜中日游戏本地化 LLM Evaluation Benchmark

**技术：** Python / pandas / Evaluation Pipeline / Taxonomy Design / Reference Annotation / Qwen3.5-9B

- 设计覆盖 15 类 Rule-addressable 与 7 类 LLM-required 问题的 22 类 taxonomy，将系统输入与一行一 Issue 的 reference annotations 分离，支持 clean、hard-negative、multi-issue 和 context-sensitive 样本。
- 构建 48 条 DEV 与 60 条独立 synthetic Held-out Test，实施 exact leakage check、DEV/Test isolation、prediction-before-annotation 和 SHA-256 freeze，控制 Prompt 调优对最终评价的污染。
- 实现 Overall、Rule、LLM、Context-sensitive 与 per-type P/R/F1，以及 FP/FN、duplicate、unknown type、clean false alarm 和 multi-issue diagnostics，基于 Bad Case 而非单一总分选择候选。
- 完成 Context 消融和 Prompt v1/v2/v2.1 受控实验；最终 Hybrid Held-out P/R/F1 为 0.5859/0.8788/0.7030，并如实记录 80% clean/hard-negative sample false-alarm 限制。

## LLM 应用 / AI 应用岗位版本

### J-GameLQA｜Rule + Context-aware LLM Hybrid QA Pipeline

**技术：** Python / pandas / Ollama / Qwen3.5-9B / Structured JSON / unittest

- 搭建从 CSV schema validation、Rule pipeline、Prompt builder、本地 Ollama provider、strict JSON parser 到统一 Issue 与评测报告的可测试 Python 流程。
- 采用 provider injection 隔离模型调用与评测逻辑；显式记录 provider、parse、schema、validation 和 duplicate failures，并在正式实验中固定 no retry/no repair，避免静默修复污染结果。
- 建立 Prompt snapshot/hash 与版本化实验流程；通过单变量 Context 对照和 Prompt v2 负实验验证改动影响，最终选择 minimal Prompt v2.1。
- 设计透明 Hybrid routing：技术类型采用 Rule，语义/语用类型采用 Context-aware LLM；最终 Held-out F1 为 0.7030，同时保留 raw traces、配置和冻结 manifest 支持审计。

## 游戏本地化 / LQA 岗位版本

### J-GameLQA｜中文→日语游戏 Localization QA 系统

**技术：** Japanese LQA / Python / Terminology QA / Context Evaluation / Qwen3.5-9B

- 从游戏 LQA 场景出发，将 Placeholder、数字、Markup、换行、UI 长度与术语一致性纳入确定性预检，并支持一条文本同时输出多个问题。
- 针对日语专项设计敬语、第一人称、角色语气、翻译腔、误译与漏译 taxonomy，把 speaker、addressee、relationship、scene 和前后文纳入判断依据。
- 构建包含对话、战斗、系统提示、教程、任务、道具、技能和 UI 等场景的原创 synthetic benchmark，并通过 hard negatives 检验合理省略、意译和强角色语气的误报风险。
- 最终系统定位为 QA assistant + human review：Held-out Recall 0.8788，同时公开 Precision 0.5859 和 hard-negative 误报问题，不把模型结果当作自动放行依据。

## 使用提醒

- 不写“上线”“服务用户”“节省工时”，因为当前没有相应证据。
- 不把 synthetic Held-out 结果称作商业效果或生产准确率。
- 面试时主动解释 Precision 较低和下一步数据计划，比回避失败结果更可信。
