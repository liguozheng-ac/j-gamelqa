# Rule Demo

这里的四条中文→日语游戏文本是为公开演示重新编写的 synthetic data，不来自 DEV、Held-out Test、商业游戏或上游项目。

- `example_input.csv` 使用与 DEV/Test 相同的无答案输入 schema。
- `example_glossary.csv` 提供两个虚构游戏术语。
- `run_rule_demo.py` 只读取这两个文件，调用现有 Rule Engine，并把 Issue JSON 打印到终端。

安装项目后运行：

```powershell
python -X utf8 examples\run_rule_demo.py
```

预期可看到：

- `DEMO_002` 缺失 `{navigator}` Placeholder。
- `DEMO_003` 使用术语“星辉护盾”的禁用译法 `スターバリア`。

其他两条用于展示规则可以正常放过合法术语、Markup 和数字。本 demo 不读取 reference annotations、不调用 LLM，也不写入 `outputs/`。
