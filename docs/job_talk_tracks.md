# Job Talk Tracks

三套话术共享同一事实，但根据岗位改变重点。不要在一次回答里把三套全部讲完。

## A. AI 数据 / 模型评测

### 30 秒

我做的 J-GameLQA 核心不是调一个 Prompt，而是建立中译日游戏 LQA 的评测流程。我定义了 22 类 taxonomy，把输入与 reference annotations 分开，构建 48 条 DEV 和 60 条独立 Held-out，并实现 P/R/F1、per-type、FP/FN、hard negative 和 multi-issue 分析。候选先在 DEV 选择，predictions 冻结后才打开 Test annotations，最后也把 Test 永久退役。

### 90 秒

数据设计上，一条样本不等于一个错误：输入表只保存 source、target 和上下文，annotation 表一行对应一个 `(string_id, issue_type)`，所以能表达 multi-issue。22 类问题分成 15 类 Rule-addressable 和 7 类 LLM-required；我同时放入 clean、hard-negative 和真正依赖人物关系的 context-sensitive case，避免 Benchmark 只测明显错误。

评测时除了 Overall F1，我还看各 scope、per-type、FP/FN、duplicate 和 protocol failures。Prompt v2 虽减少部分 mistranslation FP，却导致 keigo 等错误迁移，所以根据预设主指标拒绝；v2.1 通过 DEV gate 后才进入 Held-out。最终 Test 只打开一次，并用 hash manifest 封存。这个项目展示的是 taxonomy、数据生产思路、对照实验和 bad-case decision，而不只是 API 调用。

### 深挖追问

**Reference 怎么组织？** 输入与答案分文件；annotation 一行一个 Issue，同一 detection key 唯一，unknown type 直接 validation failure。

**如何避免 leakage？** DEV/Test 内容独立、做 exact/normalized duplicate check、Prompt 只在 DEV 调整；正式 Test 先生成并冻结 predictions，再加载 annotations。

**怎么看 FP/FN？** FP 代表人工审核成本，FN 代表遗漏风险；先看 scope 和 per-type，再看 paired cases，不能只看 Overall F1。

**为什么不做 IAA？** 当前 synthetic 数据由项目作者设计，没有第二位专业标注者；这是明确限制，下一版应双标、仲裁并报告 agreement。

## B. LLM 应用 / AI 应用

### 30 秒

我用 Python 搭了一个本地 LLM QA pipeline：CSV 输入经过 schema validation，Rule 和 Context-aware Qwen 分别处理技术与语义问题，模型输出通过 strict JSON parser 转成统一 Issue，再做 Hybrid routing 和离线评测。Provider、Prompt、parser 和 evaluation 解耦，实验固定 no retry/no repair，并保存 raw responses 与 failure diagnostics。

### 90 秒

LLM 接入不是直接在业务代码里发请求。我把 provider 作为 callable 注入 evaluator，Prompt builder 明确输入模式，response parser 校验 top-level 和 issue-level schema、string_id、severity 和 taxonomy，并区分 provider、parse、schema、validation、duplicate 五类问题。这样 unittest 用 mock provider 就能覆盖 contract，真实 Ollama 只在冻结实验中调用。

架构上也没有为了复杂而加 Agent。Placeholder 和数字交给 Rule 更稳定；LLM 专注误译、自然度和角色关系；Hybrid 按 taxonomy 路由，不做难解释的 voting。最终 Held-out Recall 较高，但 Precision 仍低，因此合理产品定位是预检助手和人工复核，而不是自动判定。

### 深挖追问

**为什么 strict JSON？** 下游需要稳定字段；无法解析必须显式成为模型表现，不能靠人工整理后当作成功。

**为什么 no retry/no repair？** 正式对照里重试会改变每个候选的机会数，自动修复也会掩盖 protocol reliability。

**为什么没有 Agent？** 当前流程是确定的 DAG，Agent 不会自动解决 FP、数据真实性或标注质量，反而增加不可控变量。

**怎么做可复现？** 保存配置、Prompt snapshot/hash、raw response、prediction、evaluation、bad cases 和 freeze manifests，并把 DEV 与 final Test 分开。

## C. 游戏本地化 / LQA

### 30 秒

J-GameLQA 是中译日游戏本地化预检，不是翻译器。规则先检查变量、数字、标签、换行、长度和术语；日语 LLM 再结合说话人、对象、关系、场景和前后文判断误译、翻译腔、敬语、自称与角色语气，最后把问题和证据交给人工 LQA。

### 90 秒

游戏文本同时有工程约束和语言约束。比如 `{player}` 丢失会造成运行或显示问题，应该确定性检查；“俺”变成“私”、部下对上司的口吻或角色固定句尾，则必须结合人物设定。我的 Context 对照中，DEV 语用子集 F1 从 0.2857 到 0.9167，说明单句质量模型不够。

但我没有把模型当裁判：Held-out Hybrid Precision 只有 0.5859，clean/hard-negative 有明显误报。真实流程里应该把它作为人工 LQA 前的风险筛选，保留 source/target span、evidence、checker 和 human-review 标记，并用审核反馈建立新的授权数据，而不是自动改译文或放行。

### 深挖追问

**为什么普通翻译质量模型不够？** 游戏还有变量、标签、UI 长度、术语和跨句角色一致性；一个总分既难定位，也可能忽略工程错误。

**为什么敬语不能只看上下级？** 剧情关系、场合和人物性格会改变 register；“下属→上司”只是证据之一，不能机械报错。

**Character Voice 怎么判断？** 依赖已建立的第一人称、句尾、词汇强度和前后文；v1 输出供人工确认，不假设模型拥有最终解释权。

**术语怎么处理？** v1 Rule 做批准/禁用译法的 exact match；语义同义词和复杂变体没有假装被规则解决。

## 高频共同问题

### 为什么你是日语专业却做这个？

我的优势不是和计算机科班竞争底层模型训练，而是把日语语言判断、游戏本地化问题和 LLM Evaluation 方法连接起来。我先从敬语、自称、角色语气、术语和技术格式这些具体问题出发，再用 Python、规则、本地模型和离线评测把判断变成可测试的工程流程。语言能力决定问题定义和 bad-case 质量，技术能力让它可复现、可比较。

### 项目痛点怎么发现的？

我是从任务结构推导，而不是声称做过客户访谈。Placeholder、Markup、数字和术语可以由传统 QA 稳定检查；敬语、自称和角色语气离不开语言与人物上下文；单纯 LLM 又会在技术问题上不稳定、在语义问题上过预测。因此自然形成 Rule + Context-aware LLM，并通过实验验证这个分工。当前需求依据仍需要未来用真实授权数据和从业者反馈加强。

### 为什么数据都是 synthetic？

商业游戏本地化语料通常涉及版权和项目保密，求职作品不应该直接搬运。因此我使用原创 synthetic benchmark，同时用 DEV/Held-out 隔离、hard negatives、multi-issue 和 context-sensitive cases 提高严谨性。这不能替代真实数据，所以结论只称 experimental performance；下一步应引入经过授权或专业人工复核的外部数据。

### 为什么 Precision 只有 0.5859？

最终 Recall 是 0.8788，说明覆盖较强；但 Precision 0.5859 表明 LLM overprediction 仍明显，10 条 clean/hard-negative 中有 8 条被 Hybrid 误报。这正是当前最大瓶颈。因此系统定位是 QA assistant + human review，不是自动放行。后续应该先在新数据上做 FP calibration，而不是隐藏数字或继续使用已退役 Test 调参。

### 如果真实上线怎么办？

顺序应该是：获得真实授权数据；制定 annotation guide；双人标注、仲裁与 IAA；建立新的 external benchmark；针对 hard negatives 和 FP 优化；补 Severity/span evaluation；设计人工 review workflow；评测 latency、cost 和 throughput；最后才考虑第二模型或更复杂架构。不能第一步就上 RAG 或 Agent。
