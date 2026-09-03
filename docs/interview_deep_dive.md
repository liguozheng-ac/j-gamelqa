# Interview Deep-Dive

这份材料用于面试口述，不是宣传稿。每个回答都可以在 30–90 秒内讲完；如果面试官追问，再打开对应 artifact 或文档。

## 30 秒版：适合 HR

我做了一个日语游戏本地化质检项目。它不是翻译器，而是检查中文原文和日语译文：程序规则负责变量、数字、标签和术语，大模型负责误译、敬语和角色语气，再用离线 Benchmark 计算 Precision、Recall、F1。我特别做了上下文消融、Prompt 负实验和独立 Held-out Test，最终混合方案在 60 条合成测试上的 F1 是 0.7030，同时我也明确保留了假阳性高、数据仍是合成的限制。

## 90 秒版：适合技术一面

J-GameLQA 解决的是中文游戏文本翻成日语后的自动预检。我的判断是 LQA 不能只靠一个 LLM：Placeholder、数字、Markup、换行和术语都有确定规则；误译、翻译腔、敬语、第一人称和角色语气才需要语义模型。所以我先实现 Rule baseline，再建立统一 Issue schema、严格 JSON 解析和 bad-case diagnostics，然后用 Qwen3.5-9B 做 Without Context 与 With Context 对照。

Development Set 上，敬语、第一人称和角色语气子集的 F1 从 0.2857 提升到 0.9167，说明游戏上下文确实重要。之后我没有一直改 Prompt 刷分：Prompt v2 因整体退化被拒绝，v2.1 用最小修改通过预注册 gate。最后只打开一次独立 60 条 Held-out Test。Hybrid v2.1 的 Precision 0.5859、Recall 0.8788、F1 0.7030。这个结果说明 Hybrid 能提高覆盖，但误报仍是最大问题。

## 3 分钟版：适合项目深挖

这个项目来自游戏本地化的实际矛盾：格式错误很机械，但语气错误高度依赖人物关系。我的输入不只有 source 和 target，还包括 speaker、addressee、relationship、scene 以及前后文。输出统一成一个 Issue，包括类型、严重度、span、evidence、checker 来源和是否需要人工复核。

系统有四层。Data 层把无答案输入和 reference annotations 分开；Rule 层检查六类确定性问题；LLM 层固定 Prompt contract，用本地 Ollama 的 Qwen3.5-9B，temperature 0、thinking off、strict JSON、no retry/no repair；Evaluation 层用 `(string_id, issue_type)` 匹配并报告 Overall、Rule-addressable、LLM-required、context-sensitive 和 FP/FN。Hybrid 不做黑盒加权，只按 taxonomy 路由。

实验上我先做 Rule baseline，再做 LLM no-context baseline，然后只改变 Context 做消融。Context-sensitive DEV F1 从 0.2857 到 0.9167，但也新增 FP，所以结论不是“上下文永远更好”，而是它对语用类问题很关键。Prompt v1 的主要 bad case 是 mistranslation overprediction；我第一次写的 v2 规则太多，错误迁移到 keigo，LLM-required 和 Hybrid 都退化，因此被拒绝。v2.1 只保留最小边界说明，通过预注册 gate 后才进入 Held-out。

最终 60 条原创 synthetic Test 有 66 个 reference detections。Hybrid v2.1 得到 TP 58、FP 41、FN 8，P/R/F1 为 0.5859/0.8788/0.7030。它比 Hybrid v1 的 0.6707 好，但 DEV→Test 仍下降 0.1491，而且 10 条 clean/hard-negative 中误报 8 条。我因此把它定位为“高召回预检 + 人工复核”，不是生产级自动裁决。下一步应该先做真人复核的外部数据和 FP calibration，而不是先堆 Agent 或 RAG。

## Q1：这个项目解决什么问题？

它在人工 LQA 前批量预检中文→日语游戏文本，找出技术格式、术语、语义和角色语用问题。输出不是“好/坏”一个分数，而是具体 Issue、证据和来源，方便审核员定位。项目也把系统当作评测对象，保留 predictions、raw responses、FP/FN 和冻结哈希。

## Q2：为什么选择游戏日语本地化？

这是我的日语优势能直接参与技术判断的场景。游戏文本比普通翻译多了变量、UI 长度、术语、角色关系、第一人称和固定语气，同一句日语脱离上下文可能完全无法判断。它适合展示语言专业能力、数据设计、Python 工程和 LLM Evaluation 的交叉价值。

## Q3：为什么 Rule 和 LLM 要分开？

两者的错误机制不同。变量或数字是否丢失可以精确比较，让 LLM 判断只会增加随机性和成本；误译、敬语和人物语气则不能靠正则可靠处理。分开后可以分别测 Rule-addressable 和 LLM-required 指标，也能明确知道最终问题来自哪一路。

## Q4：Rule Checker 有哪些？

共有 Placeholder、Number、Markup、Line Break、Length、Terminology 六类。它们分别比较变量集合、数字/小数/百分比、常见技术标签、换行数量、目标字符长度和 glossary 的批准/禁用译法。一条文本可同时触发多个 Checker，不假设一句只有一个错误。

## Q5：LLM 输入了什么？

核心是 `string_id`、中文源文、日语译文和 glossary。With Context 模式再加入文本类型、speaker、addressee、scene、relationship、context_before 和 context_after。Prompt 同时给出 22 类 taxonomy、判断边界和严格 JSON 输出 contract；模型输出随后转换成统一 Issue。

## Q6：Without Context 和 With Context 有什么区别？

两次实验除输入上下文字段外都固定：同一个 Qwen3.5-9B、Prompt v1、temperature 0、thinking off、streaming off、strict parser、无重试和修复。这样差异才主要归因于 Context，而不是模型或采样变化。

## Q7：为什么需要 Context？

因为礼貌度和角色声音是关系性的。普通体可能是好友间自然表达，也可能是侍从对国王失礼；“俺/僕/私”是否错误要看角色已建立的人设。DEV 的 context-sensitive F1 从 0.2857 到 0.9167 是支持证据，但新 FP 也提醒 Context 会诱发过度推断。

## Q8：为什么 Prompt v2 失败？

v2 为了压低 mistranslation FP 加入了较多边界规则。它确实改善部分误译判断，却把错误迁移到 keigo 等类别：LLM-required F1 从 0.7302 降到 0.6774，Hybrid 从 0.8376 降到 0.8103。这个负实验说明局部修复不能只看单类指标，也说明 Prompt 越长不一定越好。

## Q9：Prompt v2.1 怎么改的？

v2.1 回到 frozen v1，只增加最小、可解释的边界指导：语义实质改变才报 mistranslation；意义基本保留但受中文结构影响时考虑 translationese；同一根因不要重复贴标签；关系层级本身不能单独证明敬语或语气错误；evidence 要短且有依据。它在 DEV 通过事先定义的 candidate gates。

## Q10：为什么需要 DEV / Held-out Test？

DEV 可以反复看 bad cases 并调整 Prompt；如果同一批数据又当最终成绩，结果会乐观。Held-out 在候选、哈希、Hybrid policy 和评价协议确定后才打开，而且 predictions 全部冻结后才读 annotations。评测后 Test 被退役，未来开发必须用新 DEV/Test 或外部人工数据。

## Q11：Precision / Recall / F1 分别是什么意思？

Precision 问“系统报出的 Issue 里有多少是真的”，低 Precision 会浪费人工审核时间。Recall 问“参考问题里系统抓到了多少”，低 Recall 会把错误放过去。F1 是二者的调和平均，用于给单一主指标；它不是 Accuracy，也不能替代 per-type 和 bad-case 分析。

## Q12：为什么 Hybrid Precision 比 Rule 低？

Rule 只处理它有明确证据的技术问题，所以 Held-out Precision 是 0.8919。Hybrid 加入 LLM-required 预测后抓到更多语义问题，但也带来大量 FP，最终 Precision 降到 0.5859。这是高 Recall 预检系统的现实 trade-off，不应该把它包装成全面优于 Rule。

## Q13：为什么最终仍选择 Hybrid？

目标是人工 LQA 前的预检，漏掉语义问题的代价也很高。Rule Held-out Recall 只有 0.5000；Hybrid v2.1 提升到 0.8788，并在 16 个 multi-issue 样本中完整抓到 11 个、没有完全漏掉的样本。选择它的前提是 Issue 进入人工复核，而不是自动阻断发布。

## Q14：最大 Bad Case 是什么？

最大问题是过度报错。Hybrid v2.1 在 10 条 clean/hard-negative 中对 8 条至少报了一个 Issue；LLM 的 mistranslation 也有 15 个预测但只有 4 个 TP、11 个 FP。它会把合理意译、自然省略或上下文中的强烈角色语气误判为问题，直接影响审核效率。

## Q15：系统当前最大限制是什么？

不是缺 UI 或 Agent，而是证据基础还小且全为 synthetic：没有职业译者双标、仲裁和 IAA，也没有真实项目的分布、风格指南和审核成本数据。模型只有一次本地单模型实验；Severity、span、稳定性、成本与吞吐也没被正式评测。

## Q16：如果再给你两周，你会怎么继续？

第一周先写更严格的 annotation guide，找至少两名日语标注者对一批获授权或新建的外部样本独立标注，计算 agreement 并仲裁。第二周在全新 Development v2 上做 hard-negative calibration，例如二阶段核验或更保守的报告门槛，同时评测 Severity/span。已退役的 60 条 Test 不再用于任何选择；最终需要新的 Test v2 或外部评价集。
