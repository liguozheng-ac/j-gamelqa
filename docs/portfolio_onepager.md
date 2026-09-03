# J-GameLQA — Portfolio One-pager

## 项目定位

**Japanese Game Localization QA & LLM Evaluation System**

面向中文→日语游戏本地化的规则质检、上下文感知 LLM 评测与混合式 QA 系统。定位是人工 LQA 前的预检助手，不是自动翻译器或自动放行系统。

## 业务痛点

一批游戏译文里既有 Placeholder、数字、Markup、换行和术语等确定性错误，也有误译、漏译、翻译腔、敬语、第一人称和角色语气等语义/语用问题。前者适合规则，后者依赖日语能力和人物上下文；单用任何一方都不完整。

## 系统方案

```text
中文源文 + 日语译文 + 游戏上下文
            ↓
Rule Checkers      Context-aware Japanese LLM
            ↓
        Unified Issue
            ↓
        Hybrid Routing
            ↓
Evaluation Metrics + Bad Cases + Human Review
```

- Rule：Placeholder、Number、Markup、Line Break、Length、Terminology。
- LLM：Omission、Addition、Mistranslation、Translationese、Keigo、First Person、Character Voice。
- Contract：严格 JSON parser、统一 Issue schema、provider/protocol diagnostics、raw response 留存。
- Hybrid：Rule-addressable → Rule；LLM-required → Context-aware LLM。

## 技术栈

Python 3.14、pandas、openpyxl、unittest、本地 Ollama、Qwen3.5-9B、Prompt Engineering、structured JSON、SHA-256 freeze manifests。

## 实验设计

- 22 类 LQA taxonomy。
- 48 条 Development Set 用于 Prompt 与系统开发。
- 60 条独立 Held-out Test、66 个 reference detections，只做第一次也是最终一次评价。
- 对比 Rule Only、LLM No Context、LLM With Context、Prompt v1/v2/v2.1 和 Hybrid。
- 评价 Precision/Recall/F1、per-type、FP/FN、clean hard negative、multi-issue 和协议失败。

## 最终 Held-out 结果

Hybrid Prompt v2.1：`TP=58 / FP=41 / FN=8`，`Precision=0.5859 / Recall=0.8788 / F1=0.7030`。

这是 60 条原创 synthetic Held-out 样本上的 detection result，不是生产准确率。

## 最重要发现

1. Context 对敬语、第一人称和角色语气有明显价值：DEV context-sensitive F1 从 `0.2857` 到 `0.9167`。
2. Prompt 越复杂不一定越好：v2 发生错误迁移并被拒绝；最小修改 v2.1 更稳健。
3. Hybrid 提高语义问题覆盖，但 LLM overprediction 会显著降低 Precision。
4. 负实验、DEV/Test 隔离、prediction-before-annotation 和 freeze manifest，比单次漂亮分数更能说明评测质量。

## 最大限制

数据小且全为 synthetic，没有专业双标/仲裁/IAA。最终 Hybrid Recall 较高，但 clean/hard-negative sample false-alarm rate 为 80%。因此系统必须保留 Human Review；下一步应优先建立授权、人工复核的外部数据并控制 FP。
