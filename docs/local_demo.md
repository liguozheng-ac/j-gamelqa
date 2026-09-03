# Local Demo

## Purpose / 用途

J-GameLQA Local Demo 是现有 Rule + Context-aware LLM + Hybrid 系统的一层轻量 Streamlit 界面。它用于作品展示和手动试用，不是新 QA 架构，也不是 Agent、Dashboard 或自动放行系统。

## Requirements / 运行条件

- Python `>=3.11`；本项目实际在 Windows + Python `3.14.7` 验证。
- Rule Only 只需要项目 Python 环境。
- Hybrid QA 还需要本机 Ollama 服务和 `qwen3.5:9b` 模型。
- Streamlit 是 `demo` optional dependency，不属于核心 runtime 强制依赖。

## Install / 安装

在项目根目录和项目自己的虚拟环境中执行：

```powershell
cd <project-root>
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[demo]"
python -m pip check
```

本次发布准备实际验证的版本是 Streamlit `1.63.0`。`pyproject.toml` 使用 `streamlit>=1.63,<2`，允许同一主版本内的后续兼容更新。

## Start Ollama / 启动 Ollama

如果 Ollama 桌面应用没有自动启动本地服务，可以在另一个终端运行：

```powershell
ollama serve
```

Demo 使用默认本地 endpoint：`http://127.0.0.1:11434`。

## Install Model / 准备模型

```powershell
ollama pull qwen3.5:9b
ollama list
```

页面状态检查只访问 Ollama model-list API，不进行模型推理。

## Run Demo / 启动 Demo

```powershell
j-gamelqa-demo
```

命令启动 Streamlit 并显示本地 URL。CLI 不固定端口；如需无浏览器 smoke test，可选：

```powershell
j-gamelqa-demo --headless --port 8502
```

## Input / 输入

- 必填：Chinese Source、Japanese Target。
- 可选：String Type、Speaker、Addressee、Scene、Relationship、Context Before、Context After。
- 可选：Max Length；留空时由现有 Length Checker 按原行为跳过。
- 可选：Glossary 表格，沿用 `source_term`、`approved_ja`、`forbidden_ja` schema；留空不会自动载入项目 glossary。

页面提供三条全新原创 synthetic 示例：placeholder 缺失、依赖人物关系的敬语问题、正常译文。它们只用于 Demo，不属于 DEV 或 Held-out Test。

## Architecture / 工作结构

```text
Manual Source / Target / Context
               ↓
         thin demo_service
          ↙             ↘
existing Rule Engine   Prompt v2.1 WITH_CONTEXT
                       → Ollama → Strict Parser
          ↘             ↙
       existing Hybrid policy
               ↓
       Unified Issue objects
               ↓
       Streamlit presentation
```

`demo_service` 只负责把单条表单输入转换成现有 record/glossary 结构，并组织已有 API 调用。规则判断、Prompt 内容、JSON 解析和 Hybrid 路由都没有在 UI 中重写。

## Modes / 运行模式

### Rule Only / 仅规则质检

调用现有 Rule Engine。即使 Ollama 不可用也能运行，适合检查 placeholder、数字、markup、换行、长度和术语。

### Hybrid QA / 混合式质检

按冻结配置执行：

```text
Rule Engine
+ Prompt v2.1 With Context
+ qwen3.5:9b (temperature 0, thinking false, streaming false)
+ existing strict parser (no retry, no repair)
+ existing Hybrid routing policy
```

页面分别展示 Rule Issues、LLM Issues 和 Hybrid Issues，并保留折叠的 raw LLM response 与精简 protocol diagnostics。

## Error Handling / 错误处理

- 空源文、空译文或非法 Max Length：在表单下显示可修正提示。
- Ollama 或模型不可用：Hybrid 显示启动说明，Rule Only 继续可用。
- HTTP/provider failure：显示精简错误类别，不向普通用户展开 Python traceback。
- JSON parse、schema 或 string-id validation failure：显示 `LLM protocol failure`；不 repair、不 retry，也不进行隐藏的第二次模型调用。

## Held-out Isolation / 留出集隔离

Demo runtime 不读取 `data/dev_annotations.csv`、`data/test.csv` 或 `data/test_annotations.csv`，也不生成 benchmark metrics。页面中的历史 F1 仅位于折叠的 Project Info 区域，并明确标为 60 条原创 synthetic Held-out Test 上的冻结历史结果，而非生产准确率。

## Known Limitations / 已知限制

- 当前只有本地单条输入，没有批量上传、用户系统、数据库或云部署。
- LLM 假阳性仍明显，因此 Hybrid 输出必须由人复核。
- 状态检查只能确认本地服务和模型列表，不能保证下一次推理一定成功。
- Demo 不提供 JSON repair、自动重试或自动改写译文。
- 当前没有随仓库提供 GUI 截图；可在本机启动后进行真实截图。
