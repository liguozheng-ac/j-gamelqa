# 数据与 Reference Annotation Schema

`data/pilot.csv` 是 J-GameLQA 的早期开发数据。每一行表示一条需要检查的中文源文、日语译文及其游戏上下文。

| 字段 | 大白话说明 |
| --- | --- |
| `string_id` | 这条文本的唯一编号，方便报告问题和回查原始记录。 |
| `source_zh` | 游戏中的中文源文，是判断日语译文是否准确的主要依据。 |
| `target_ja` | 需要接受 QA 检查的日语译文。它可以正确，也可以故意包含一种测试错误。 |
| `string_type` | 文本在游戏里的用途，例如角色对白、系统提示或任务目标。 |
| `speaker` | 谁说出或发出这条文本；系统文本可以填写“系统”。 |
| `addressee` | 这句话说给谁听，用于判断敬语、称呼和语气是否合适。 |
| `scene` | 文本出现的地点或剧情场景，帮助理解这句话发生在什么环境中。 |
| `relationship` | 说话者与听话者的关系，以及与语言风格直接有关的角色设定。 |
| `context_before` | 这句话之前发生的事情或上一段语境，用来减少孤立判断。 |
| `context_after` | 这句话之后发生的事情或下一段语境，用来验证理解是否连贯。 |
| `max_length` | 译文建议允许的最大字符数，用于以后检查 UI 空间限制；当前 pilot 只记录限制，不执行检查。 |
| `expected_issue` | 开发阶段预期发现的主要问题类型；正确样例使用 `none`。它只是 synthetic pilot 标签，不是正式 Gold Label。 |
| `expected_severity` | 开发阶段预期的问题严重度；当前使用 `minor`、`major`、`critical`，正确样例使用 `none`。 |

## 当前标签范围

- `none`：没有预设错误。
- `placeholder_missing`：源文变量在译文中消失。
- `placeholder_modified`：变量名称或格式被错误修改。
- `number_mismatch`：源文和译文中的数字不一致。
- `omission`：源文的重要内容没有翻译。
- `mistranslation`：译文表达了错误或相反的意思。
- `translationese`：日语虽然能猜懂，但表达生硬，带有明显翻译腔。
- `keigo_mismatch`：敬语或礼貌程度不符合人物关系。
- `first_person_mismatch`：角色第一人称与设定不一致。
- `character_voice_mismatch`：角色语气或句尾与角色设定不一致。

这些标签只服务于 Early Prototype 开发，不代表最终 Error Taxonomy。

## Development / Held-out Test 输入

### `data/dev.csv`

`dev.csv` 是 Rule Engine 和未来模型看到的 system input。它与答案分离，不允许包含 `expected_issue`、`expected_severity` 或其他 reference annotation 字段。

| 字段 | 含义 |
| --- | --- |
| `string_id` | 文本的唯一标识，不能为空或重复。 |
| `source_zh` | 中文源文。 |
| `target_ja` | 待检查的日语译文。 |
| `string_type` | 对白、系统消息、任务目标等文本类型。 |
| `speaker` | 说话者或“系统”。 |
| `addressee` | 听话者或消息接收者。 |
| `scene` | 文本出现的游戏场景。 |
| `relationship` | 人物关系及与语言风格有关的角色设定。 |
| `context_before` | 前文或此前事件。 |
| `context_after` | 后文或后续事件。 |
| `max_length` | 当前 Rule Baseline 使用的正整数目标字符上限。 |

`data/test.csv` 完全复用以上 11 个输入字段，并使用 `TEST_001` 至 `TEST_060`。两者都禁止出现 `expected_issue`、`expected_severity`、`answer`、`label` 等答案泄漏字段。

### `data/dev_annotations.csv`

`dev_annotations.csv` 保存 reference annotations，一行对应一个 reference Issue。

| 字段 | 含义 |
| --- | --- |
| `annotation_id` | Annotation 的唯一编号。 |
| `string_id` | 对应 `dev.csv` 中的文本编号。 |
| `issue_type` | Taxonomy 中已经注册的问题类型。 |
| `severity` | Reference 严重度，当前允许 `minor`、`major`、`critical`。 |
| `source_span` | 与问题有关的中文片段；允许为空。 |
| `target_span` | 与问题有关的日语片段；允许为空。 |
| `evidence` | 支持判断的 JSON 证据。 |
| `annotation_note` | 给开发者或人工复核者阅读的说明。 |

同一个 `string_id` 可以有多个不同的 `issue_type`。Clean sample 可以不存在任何 annotation 行。Reference 中 `(string_id, issue_type)` 必须唯一；一个相同类型的问题即使涉及多个片段，也应合并为一条 annotation，并在 span、evidence 和 note 中记录细节。

`data/test_annotations.csv` 完全复用这套 8 字段 annotation schema。它只在最终评测阶段作为 reference 读取，不应进入 Prompt、Rule 输入或开发期 bad-case feedback。

### `data/benchmark_manifest.json`

Manifest 只记录 Development/Test 的用途、规模、composition、设计 ID 列表和冻结 Test 文件哈希。它不是 Dataset Registry，也不应作为模型输入。Test 文件一旦冻结，哈希变化必须导致静态 validation failure。

## Benchmark v1 Detection Evaluation

- 唯一 matching key：`(string_id, issue_type)`。
- Severity 不参与 TP、FP、FN 判定，原值仍然保留。
- `source_span` 和 `target_span` 不参与 detection matching，保留用于 evidence、人工复核、Bad Case Analysis 及未来 Localization Evaluation。
- Prediction duplicate detection key 只计算一次，但 `duplicate_predictions` 必须报告其 count。
- Unknown reference issue type 会直接导致 validation failure。
- Unknown prediction issue type 不会被过滤；它参与 Overall Evaluation，并单独出现在 `unknown_prediction_types` 和 occurrence diagnostics 中。
- 每个 Per-Issue-Type 结果包含 `reference_count` 和 `prediction_count`；零分母时 Precision、Recall、F1 仍保存为数值 `0.0`。
- 当前没有正式 Severity Evaluation。
- 当前没有正式 Localization/Span Evaluation。

Development 和 Test 中的答案都应称为 reference annotations，而不是 Gold annotations。两套数据均为 synthetic，尚未经过正式多标注者流程；Held-out 只表示未用于系统开发，不表示生产级代表性。
