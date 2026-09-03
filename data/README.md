# Development Data

`pilot.csv` 包含 10 条原创的中文到日语游戏本地化合成样例，用于早期开发和规则调试。

- 文件编码：UTF-8
- 数据性质：synthetic pilot
- 数据来源：项目自建的虚构游戏场景和对白
- 当前用途：验证字段设计，并为后续确定性 Rule QA 提供最小输入

这些数据没有经过正式标注流程、双人复核或一致性检验，因此不是 Benchmark，也不是 Gold Dataset。

## Development Set

`dev.csv` 是系统输入，只包含中文源文、日语译文和游戏上下文，不包含任何 reference annotation 字段。

`dev_annotations.csv` 保存 reference annotations，一行表示一个 `(string_id, issue_type)` detection。一个 string 可以有多个不同的 issue type；clean sample 可以完全没有 annotation 行。

当前数据是由 48 条原创游戏本地化样本构成的 synthetic development benchmark，用于开发和验证 Evaluation Harness，不代表真实业务数据，也没有经过正式多标注者流程。它包含 clean、single-issue、multi-issue、hard-negative 与需要上下文才能判断的样本。

Development Set 可以用于 Prompt 开发、Rule 改进、taxonomy 调整、bad-case analysis 和实验探索，因此它不是最终泛化评测集。

Benchmark v1 规则：

- Detection key 是 `(string_id, issue_type)`。
- Reference detection key 必须唯一。
- Prediction duplicate 会去重计算，但必须作为诊断报告。
- Severity 和 span 保留，但不参与本轮 detection matching。
- Unknown reference issue type 会导致 validation failure。
- Unknown prediction issue type 不会被删除；它会参与 Overall Evaluation，并在没有对应 reference 时计为 FP。
- Per-Issue-Type 同时报告 `reference_count` 与 `prediction_count`，用来区分“该类型没有样本”和“系统没有检出”。
- 本轮不进行正式 Severity Evaluation 或 Localization/Span Evaluation。

## Held-out Test Set

`test.csv` 和 `test_annotations.csv` 是与 Development Set 独立创作的 synthetic held-out Test Set：

- 60 个 samples
- 66 个 reference detections
- 10 clean / hard-negative samples
- 34 single-issue samples
- 16 multi-issue samples
- 15 个 Rule-addressable 类型均至少有 2 个 references
- 7 个 LLM-required 类型均至少有 4 个 references
- 17 个 context-sensitive samples

Test 输入与 DEV 使用相同 schema，annotation 也使用相同 `(string_id, issue_type)` detection contract。`benchmark_manifest.json` 保存 split 用途、composition、ID 列表和 Test 文件 SHA-256。

The held-out synthetic test set is reserved for final evaluation and must not be used for prompt tuning.

禁止使用 Test 进行 Prompt 调优、few-shot 选择、Rule 特判或反复查看分数。Stage 7A 没有生成任何 Test prediction 或 evaluation artifact。
