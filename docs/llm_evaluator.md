# Japanese LLM Evaluator Contract v1

阶段 6A 定义模型无关的 Japanese LLM Evaluator 协议。本阶段没有连接 Ollama、API 或任何本地/远程推理服务；测试中的模型回复全部由 fake provider 提供。

## Input Modes

WITHOUT_CONTEXT 输入：

- string_id
- source_zh
- target_ja
- string_type
- max_length
- applicable_glossary_constraints

WITH_CONTEXT 在完全相同的基础输入上增加：

- speaker
- addressee
- scene
- relationship
- context_before
- context_after

两种模式调用同一个 Prompt Builder。实验变量只有这些上下文字段，taxonomy、definitions、输出协议和主体指令保持一致。

## Glossary Handling

Glossary 使用确定性字符串匹配，不使用 RAG。

只有 source_zh 中实际出现的 source_term 会进入 applicable_glossary_constraints。每条约束包含：

    {
      "source_term": "传送门",
      "approved_ja": "転送門",
      "forbidden_ja": ["ポータル"]
    }

两种输入模式获得完全相同的 glossary constraints。

## Prompt v1

Prompt v1 是 zero-shot structured evaluator，只包含：

1. Role and task
2. Registered issue types and concise definitions
3. Evaluation rules
4. Controlled input payload
5. Required JSON contract

Prompt 明确允许 clean translation 返回空 issues，也允许一个 string 返回多个不同 issue types。Prompt 不包含 few-shot、chain-of-thought、self-reflection、self-consistency、prompt ensemble 或 agent loop。

全部 issue type 和 definition 均来自 taxonomy.py 中的 ISSUE_TYPE_DEFINITIONS。Prompt 不维护第二份 type list。

## Output JSON Contract

Clean response：

    {
      "string_id": "DEV_011",
      "issues": []
    }

Issue response：

    {
      "string_id": "DEV_040",
      "issues": [
        {
          "issue_type": "keigo_mismatch",
          "severity": "major",
          "source_span": "",
          "target_span": "命令を出せ",
          "evidence": "A subordinate uses a command form when addressing a superior."
        }
      ]
    }

不支持 confidence、probability 或 score。

## Parsing and Validation

协议执行：

    raw response
        ↓
    strict JSON parsing
        ↓
    top-level and issue schema validation
        ↓
    expected string_id validation
        ↓
    Issue conversion

只接受 JSON object。顶层字段必须正好是 string_id 和 issues。每个 issue 必须正好包含：

- issue_type：非空字符串
- severity：minor、major 或 critical
- source_span：字符串，允许为空
- target_span：字符串，允许为空
- evidence：非空英文简短说明

不会从 Markdown code fence 或自然语言中猜测 JSON，也不会静默修正错误字段。

raw_response 始终保存在 LLMParseResult 中。JSON 损坏和模型正常返回 clean 是两个可区分结果。

## Diagnostics

LLMProtocolDiagnostics 分别保存：

- parse_failures：无法解析为 JSON
- schema_failures：字段缺失、多余或类型错误
- validation_failures：例如 response string_id 与请求不一致
- unknown_issue_types：结构合法但 taxonomy 未注册的类型
- duplicate_predictions：同一次回复内重复的 detection key 及其 count

任一结构性失败都会使该 response 产生零个 Issue，但 raw_response 会保留。

Unknown issue_type 不属于 schema failure。它会保留为 japanese_llm prediction，并交给现有 Evaluation Harness 作为 unknown prediction 处理，不自动映射也不静默删除。

Duplicate prediction 不通过 set 删除。原始 Issue 会全部保留；现有 Evaluation Harness 使用 string_id 和 issue_type 作为 detection key 去重计分，同时报告 duplicate。

## Issue Conversion

合法预测转换为项目已有的 Issue：

- checker = japanese_llm
- issue_type、severity 和 span 使用模型输出
- evidence 保存为 reason
- needs_human_review = True

空 issues 转换为零个 Issue 对象。

Severity 和 span 保留用于人工复核与 bad-case analysis，但不参与 Benchmark v1 detection matching。

## Hybrid v1

Hybrid merge 的输入是彼此独立的 rule_predictions 和完整 llm_predictions：

    LLM raw predictions
        ├── LLM Only Evaluation
        └── Hybrid filter

Hybrid 规则：

1. 保留所有 Rule predictions。
2. 只加入 issue_type 属于 LLM_REQUIRED_ISSUE_TYPES 的 LLM predictions。
3. Rule-addressable、unknown 或其他不属于 LLM 职责的 LLM prediction 进入 llm_predictions_excluded_from_hybrid。
4. Merge 后的重复 detection key 保留并记录，由 Evaluation Harness 去重计分。

Hybrid filter 不会修改传入的 LLM prediction list，因此 LLM Only 仍可评估全部 LLM 输出。

## Provider Boundary

run_llm_evaluator 接收一个 callable provider：

    prompt string -> raw response string

阶段 6A 测试注入 fake provider。未来 Ollama、本地模型或 API adapter 只需遵守这个边界，后续解析和评测逻辑不需要随模型变化。

## Stage 6B: Qwen3.5-9B Without Context Baseline

首次真实 LLM baseline 已使用以下固定配置完成：

    experiment_id: qwen35_9b_no_context_v1
    model: qwen3.5:9b
    provider: local Ollama HTTP /api/generate
    input_mode: without_context
    prompt_version: v1
    temperature: 0
    thinking: false
    stream: false
    structured_output: false
    retry: false
    repair: false
    timeout_seconds: 120
    dataset: 48-item synthetic development benchmark v1

Provider 使用 Python 标准库 urllib，不依赖 Ollama SDK。请求没有 format 或 JSON schema 字段，因此模型只依靠 Prompt v1 遵守输出协议。

Inference 阶段只读取 dev.csv 与 glossary.csv。全部模型调用完成后，Evaluation 阶段才读取 dev_annotations.csv。

Raw JSONL 逐条写入，可在中断后使用 resume 跳过已经记录的 string_id。首次完整结果生成后，runner 拒绝覆盖 predictions、evaluation 和 bad-case artifacts。

### Protocol Metrics

protocol_success_rate 定义为：

    通过 JSON、schema 和 string_id validation 的 response 数
    /
    成功完成的 provider 调用数

Provider failure 不进入分母，但会单独统计。Protocol failure 不转换为 clean；它产生零个 prediction，使对应 reference detection 自然成为 FN。

首次完整运行：

    total_requests: 48
    successful_provider_calls: 48
    provider_failures: 0
    protocol_successful_responses: 48
    parse_failures: 0
    schema_failures: 0
    validation_failures: 0
    unknown_issue_types: 0
    duplicate_prediction_keys: 0
    protocol_success_rate: 1.0
    thinking_content_responses: 0
    mean_latency_seconds: 1.5561
    median_latency_seconds: 1.5828

### Detection Results

LLM Only / Without Context：

    Overall Micro
    TP: 25
    FP: 17
    FN: 26
    Precision: 0.5952
    Recall: 0.4902
    F1: 0.5376

    LLM-required Micro
    TP: 13
    FP: 15
    FN: 12
    Precision: 0.4643
    Recall: 0.5200
    F1: 0.4906

这是首次完整 baseline 的封存结果，没有在运行后修改 Prompt v1、taxonomy、parser 或 reference annotations。阶段 6B 没有运行 With Context 或正式 Hybrid 指标。

### Baseline Artifacts

- outputs/qwen35_9b_no_context_config.json
- outputs/qwen35_9b_no_context_raw.jsonl
- outputs/qwen35_9b_no_context_predictions.json
- outputs/qwen35_9b_no_context_evaluation.json
- outputs/qwen35_9b_no_context_bad_cases.json

## Stage 6C: Qwen3.5-9B With Context Controlled Baseline

阶段 6C 直接读取封存的阶段 6B artifacts，不重新生成 No Context 回复。新实验保持相同的模型、48 条数据、Glossary、Prompt v1、22 类 taxonomy、temperature 0、thinking off、streaming off、strict parser、no retry / repair、无 structured output 和 120 秒 timeout；唯一计划内变量是 `input_mode: with_context`。

With Context 在基础输入之外加入 `speaker`、`addressee`、`scene`、`relationship`、`context_before`、`context_after`。Inference 仍不读取 reference annotations。

### With Context Runtime and Protocol

    total_requests: 48
    successful_provider_calls: 48
    provider_failures: 0
    protocol_successful_responses: 48
    parse_failures: 0
    schema_failures: 0
    validation_failures: 0
    unknown_issue_types: 0
    duplicate_prediction_keys: 1
    protocol_success_rate: 1.0
    thinking_content_responses: 0
    raw_predictions: 53
    unique_detection_keys: 52
    mean_latency_seconds: 2.0025
    median_latency_seconds: 1.6199
    min_latency_seconds: 0.5560
    max_latency_seconds: 5.3407

唯一重复 detection key 是 `DEV_012 / omission`，出现 2 次；Evaluation Harness 按 detection key 去重计分，同时保留 duplicate diagnostic。

### Controlled Detection Results

    With Context Overall Micro
    TP: 34, FP: 18, FN: 17
    Precision: 0.6538, Recall: 0.6667, F1: 0.6602

    With Context LLM-required Micro
    TP: 23, FP: 15, FN: 2
    Precision: 0.6053, Recall: 0.9200, F1: 0.7302

    With Context Rule-addressable LLM Only
    TP: 11, FP: 3, FN: 15
    Precision: 0.7857, Recall: 0.4231, F1: 0.5500

与封存的 No Context 相比：

    Overall delta: TP +9, FP +1, FN -9, F1 +0.1226
    LLM-required delta: TP +10, FP +0, FN -10, F1 +0.2396

分析用 context-sensitive subset 只包含 `keigo_mismatch`、`first_person_mismatch`、`character_voice_mismatch`，不改变正式 taxonomy：

    No Context: TP 2, FP 1, FN 9, P 0.6667, R 0.1818, F1 0.2857
    With Context: TP 11, FP 2, FN 0, P 0.8462, R 1.0000, F1 0.9167
    Delta: TP +9, FP +1, FN -9, P +0.1795, R +0.8182, F1 +0.6310

Paired analysis 找到 11 个 FN→TP、2 个 TP→FN、6 个新增 FP 和 5 个消失的 FP。敬语 recall 从 0.25 升至 1.00，第一人称 recall 从 0.3333 升至 1.00，角色语气 recall 从 0 升至 1.00。与此同时，`DEV_007 / keigo_mismatch` 与 `DEV_008 / character_voice_mismatch` 成为新的上下文过度解读误报。

`mistranslation` 的 prediction_count 从 12 降至 11，FP 从 8 降至 7，precision 从 0.3333 小幅升至 0.3636；过预测仍然严重。`DEV_034` 从正确的 `translationese` 回退为错误的 `mistranslation`，说明上下文没有稳定解决 taxonomy 边界混淆。

该对照支持的结论是：在这份小型 synthetic development benchmark 上，上下文对敬语、固定第一人称和角色语气判断有明显帮助；但新增上下文也会诱发过度推断，不能据此声称在真实生产数据上普遍有效。

### Stage 6C Artifacts

- outputs/qwen35_9b_with_context_config.json
- outputs/qwen35_9b_with_context_raw.jsonl
- outputs/qwen35_9b_with_context_predictions.json
- outputs/qwen35_9b_with_context_evaluation.json
- outputs/qwen35_9b_with_context_bad_cases.json
- outputs/qwen35_9b_context_comparison.json

## Stage 6D: Rule + Context-aware LLM Hybrid Baseline

Hybrid v1 使用阶段 6A 已定义的透明职责边界：

    Rule-addressable types <- 所有封存 Rule predictions
    LLM-required types     <- 封存 With Context LLM predictions

With Context LLM 输出中的 Rule-addressable 和 unknown 类型不会进入 Hybrid，并保存在 merge diagnostics。合并不做置信度过滤、投票、仲裁或手工修正。

本阶段只读取 Rule、No Context 和 With Context 的现有 artifacts，没有调用 Ollama，也没有重新生成任何 LLM prediction。53 个 With Context raw predictions 中，39 个 LLM-required predictions 被接纳，14 个 Rule-addressable predictions 被排除；unknown 为 0。Hybrid 共保留 67 个 raw predictions、66 个唯一 detection keys，重复项仍为 `DEV_012 / omission`。

### Four-method Overall Comparison

| Method | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| Rule Only | 26 | 2 | 25 | 0.9286 | 0.5098 | 0.6582 |
| LLM Only — Without Context | 25 | 17 | 26 | 0.5952 | 0.4902 | 0.5376 |
| LLM Only — With Context | 34 | 18 | 17 | 0.6538 | 0.6667 | 0.6602 |
| Rule + Context-aware LLM Hybrid | 49 | 17 | 2 | 0.7424 | 0.9608 | 0.8376 |

Hybrid 的 Rule-addressable 指标与 Rule Only 完全相同：TP 26、FP 2、FN 0、F1 0.9630。LLM-required 指标与 With Context LLM 完全相同：TP 23、FP 15、FN 2、F1 0.7302。Context-sensitive subset 也完整保留阶段 6C 的结果：TP 11、FP 2、FN 0、F1 0.9167。

相对 Rule Only，Hybrid 从 25 个语义/语用 FN 中补回 23 个，同时新增 15 个 LLM FP。相对 With Context LLM，Rule 补回 15 个技术类 FN；移除 LLM 的 3 个技术类 FP 后又继承 Rule 自身 2 个 FP，因此 overall FP 净减少 1。

Hybrid 的 17 个 FP 中，2 个来自 Rule（`DEV_015 / number_extra`、`DEV_017 / terminology_forbidden`），15 个来自 LLM。剩余 2 个 FN 都是 `translationese`：`DEV_007` 与 `DEV_034`。这说明简单职责分工形成了明显互补，但 Precision 仍主要受 LLM semantic overprediction 限制。

### Stage 6D Artifacts

- outputs/hybrid_rule_qwen35_context_config.json
- outputs/hybrid_rule_qwen35_context_predictions.json
- outputs/hybrid_rule_qwen35_context_evaluation.json
- outputs/hybrid_rule_qwen35_context_bad_cases.json
- outputs/method_comparison_v1.json
- outputs/method_comparison_v1.csv

## Stage 7A: V1 Freeze and Held-out Test Policy

阶段 6B–6D 的 Development Set 实验已冻结。19 个已有实验 artifact 及 Prompt、taxonomy、Hybrid、evaluation contract 的 SHA-256 记录在 `outputs/v1_experiment_freeze_manifest.json`。当前四方法数字不再修改或重新运行。

Prompt v1 的可读快照位于 `docs/prompt_v1_snapshot.md`。Without Context 与 With Context 示例均由真实 `build_evaluator_prompt` 生成，使用专门的文档 demo，不使用 Held-out Test 样本。Prompt v1 源码未修改。

新增 `data/test.csv` 与 `data/test_annotations.csv` 作为 60 条 synthetic held-out Test Set。Stage 7A 仅执行 schema、reference consistency、taxonomy coverage、composition、SHA-256 和 DEV/TEST exact/normalized duplicate 检查。没有调用 provider，没有生成 Test predictions，也没有查看 Test metrics。

## Stage 7B: Prompt v2 Development Optimization

Prompt v2 作为独立 Builder 建立在冻结 Prompt v1 之上，只增加一般性的 taxonomy boundary 与 final consistency guidance；Prompt v1、22 类 taxonomy、strict parser、JSON contract、Rule 和 DEV reference annotations 均未修改。真实 Prompt v2 快照位于 `docs/prompt_v2_snapshot.md`。

正式实验只运行一次：48 条 DEV、Qwen3.5-9B、With Context、temperature 0、thinking off、no retry / repair、无 structured output。48 次 provider 请求全部成功；47 个响应通过严格协议，`DEV_016` 因模型把长篇内部判断写入 evidence 并产生无效 JSON 引号而 parse failure。没有重试或修复。

Prompt v2 LLM-required 为 TP 21、FP 16、FN 4、P 0.5676、R 0.8400、F1 0.6774；相对 v1 的 F1 0.7302 回退。Hybrid + Prompt v2 为 TP 47、FP 18、FN 4、P 0.7231、R 0.9216、F1 0.8103；相对 Hybrid v1 的 F1 0.8376 也回退。`mistranslation` FP 从 7 降至 5，但 `keigo_mismatch` FP 从 1 增至 4，说明局部 taxonomy 改善没有转化为整体提升。完整结果与 paired bad-case 分析见 `docs/prompt_v2_development_results.md`。

本阶段没有读取 Held-out Test 内容进行 Prompt 开发，没有运行 Test inference，也没有产生或查看 Test metrics。

## Stage 7B.1: Prompt v2.1 Final Development Experiment

Prompt v2.1 是直接建立在冻结 Prompt v1 上的最小减法版本，不继承 Prompt v2 的长篇 omission/addition、specific-type priority、technical-versus-semantic hierarchy 或 final checklist。正式推理前已固定 Candidate Gate，要求 LLM-required P > 0.6053、R >= 0.8800、F1 >= 0.7302、Hybrid F1 >= 0.8376，并且 48/48 strict-protocol 成功、provider failure 为零。

唯一一次正式实验保持 48 DEV、Qwen3.5-9B、With Context、temperature 0、thinking off、no retry/repair、无 structured output。结果为 48/48 protocol success，parse/schema/validation failure 均为 0。LLM-required 为 TP 23、FP 13、FN 2、P 0.6389、R 0.9200、F1 0.7541；Hybrid 为 TP 49、FP 15、FN 2、P 0.7656、R 0.9608、F1 0.8522。

五项 Candidate Gate 全部通过，因此 Prompt v1 与 Prompt v2.1 成为两个 held-out candidates。Prompt v2 保持 rejected experimental candidate。不会继续进行 Prompt v2.2/v3 DEV hill-climbing。完整三版比较、重点类型和 paired bad cases 见 `docs/prompt_v21_development_results.md`。

本阶段没有 Test inference、Test metrics 或 Test bad-case inspection。

## Stage 7C: First and Final Held-out Evaluation

Stage 7C 首次正式打开 60 条 original synthetic held-out Test Set。评测协议先以 SHA-256 `39E01B0C1507A55D34CDAFB1F4E0421B5654FDCBC96BBD6045D192CF11BC06A2` 冻结；Rule、Prompt v1 和 Prompt v2.1 predictions 全部生成并计算哈希后，才加载 reference annotations。

Held-out Overall F1 分别为：Rule 0.6408、LLM Prompt v1 0.4789、LLM Prompt v2.1 0.5175、Hybrid v1 0.6707、Hybrid v2.1 0.7030。Hybrid v2.1 相对 Hybrid v1 的 F1 差为 +0.0323，超过预注册的 `< 0.02` broadly comparable 区间，因此在描述性口径下选为最终原型版本；不声称统计显著。

v2.1 的 mistranslation FP 从 17 降到 11，character voice F1 从 0.5000 升到 0.8333，但 translationese F1 从 0.7500 降到 0.5000，keigo F1 从 0.7273 降到 0.5714。Hybrid v2.1 对 10 个 clean/hard-negative 样本中的 8 个产生至少一个报警，说明整体 Precision 和边界判断仍不足。

完整协议见 `docs/heldout_evaluation_protocol.md`，结果与限制见 `docs/heldout_evaluation_results.md`。Held-out artifacts 已记录在 `outputs/heldout_evaluation_freeze_manifest.json`。该 Test Set 从此不得用于调优；未来开发需要 Test v2 或 external/human-reviewed evaluation set。
