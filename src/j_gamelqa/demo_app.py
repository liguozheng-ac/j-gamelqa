"""Streamlit presentation layer for the J-GameLQA local demo."""

import pandas as pd
import streamlit as st

from j_gamelqa.demo_service import (
    DEMO_ENDPOINT,
    DEMO_EXAMPLES,
    DEMO_MODEL,
    ISSUE_TYPE_LABELS_ZH,
    STRING_TYPE_OPTIONS,
    DemoInputError,
    DemoProviderFailure,
    DemoRunResult,
    build_demo_record,
    check_ollama_status,
    prepare_glossary,
    run_hybrid_qa,
    run_rule_only,
)
from j_gamelqa.io import REQUIRED_GLOSSARY_FIELDS
from j_gamelqa.models import Issue


st.set_page_config(page_title="J-GameLQA", page_icon="🔎", layout="wide")


@st.cache_data(ttl=5, show_spinner=False)
def _cached_ollama_status():
    return check_ollama_status()


def _initialize_state() -> None:
    first_example = next(iter(DEMO_EXAMPLES.values()))
    for key, value in first_example.items():
        st.session_state.setdefault(f"demo_{key}", value)


def _load_example(example_name: str) -> None:
    for key, value in DEMO_EXAMPLES[example_name].items():
        st.session_state[f"demo_{key}"] = value


def _display_issues(issues: list[Issue]) -> None:
    if not issues:
        st.success("No issues detected. / 未检测到问题。")
        st.caption(
            "This does not guarantee production-ready translation quality. / "
            "这并不代表译文已经达到生产级质量。"
        )
        return

    for issue in issues:
        chinese_name = ISSUE_TYPE_LABELS_ZH.get(issue.issue_type, "未知类型")
        with st.container(border=True):
            st.markdown(f"#### `{issue.issue_type}` · {chinese_name}")
            left, right = st.columns(2)
            left.write(f"**Severity / 严重程度：** `{issue.severity}`")
            right.write(f"**Checker / 检查来源：** `{issue.checker}`")
            left.write(f"**Source Span / 原文片段：** {issue.source_span or '—'}")
            right.write(f"**Target Span / 译文片段：** {issue.target_span or '—'}")
            st.write("**Evidence / 判断依据：**")
            st.json(issue.evidence)
            review_text = "Yes / 是" if issue.needs_human_review else "No / 否"
            st.write(f"**Needs Human Review / 是否需要人工复核：** {review_text}")


def _display_result(result: DemoRunResult) -> None:
    st.divider()
    st.subheader("QA Results / 质检结果")
    rule_col, llm_col, hybrid_col = st.columns(3)
    rule_col.metric("Rule Issues / 规则问题", len(result.rule_issues))
    llm_col.metric("LLM Issues / 大模型问题", len(result.llm_issues))
    hybrid_col.metric("Hybrid Issues / 最终问题", len(result.hybrid_issues))

    if result.mode == "hybrid":
        if result.protocol_success is False:
            st.error("LLM protocol failure / 大模型协议失败")
        tabs = st.tabs(
            [
                "Rule Issues / 规则问题",
                "LLM Issues / 大模型问题",
                "Hybrid Issues / 混合最终问题",
            ]
        )
        with tabs[0]:
            _display_issues(result.rule_issues)
        with tabs[1]:
            _display_issues(result.llm_issues)
        with tabs[2]:
            _display_issues(result.hybrid_issues)
            st.info(
                "J-GameLQA is designed as a QA assistant, not an automatic "
                "acceptance system. / J-GameLQA 定位为质检辅助系统，而非自动放行系统。"
            )

        if result.raw_llm_response is not None:
            with st.expander("Raw LLM Response / 大模型原始响应"):
                st.code(result.raw_llm_response, language="json")
        if (
            result.protocol_success is False
            or any(result.protocol_diagnostics.values())
            or result.excluded_llm_issues
            or result.duplicate_predictions
        ):
            with st.expander("Technical Details / 技术详情"):
                st.json(
                    {
                        "protocol_success": result.protocol_success,
                        "protocol_diagnostics": result.protocol_diagnostics,
                        "excluded_llm_issue_types": [
                            issue.issue_type for issue in result.excluded_llm_issues
                        ],
                        "duplicate_predictions": result.duplicate_predictions,
                        "latency_seconds": result.latency_seconds,
                    }
                )
    else:
        _display_issues(result.rule_issues)


_initialize_state()

st.title("J-GameLQA")
st.subheader("Japanese Game Localization QA / 日语游戏本地化质检")
st.write("Rule-based deterministic QA + Context-aware LLM evaluation")
st.caption("确定性规则质检 + 上下文感知大模型评测")

with st.sidebar:
    st.header("Runtime / 运行状态")
    st.write("**LLM Provider / 大模型提供端**")
    st.code("Ollama")
    st.write("**Model / 模型**")
    st.code(DEMO_MODEL)
    st.write("**Endpoint / 本地接口**")
    st.code(DEMO_ENDPOINT.replace("http://", "").removesuffix("/api/generate"))
    if st.button("Refresh Status / 刷新状态"):
        _cached_ollama_status.clear()
    ollama_status = _cached_ollama_status()
    if ollama_status.service == "available":
        st.success("Ollama: Available / 可用")
    else:
        st.warning("Ollama: Unavailable / 不可用")
    if ollama_status.model == "available":
        st.success(f"Model: Available / {DEMO_MODEL} 可用")
    elif ollama_status.model == "unavailable":
        st.warning(f"Model: Unavailable / {DEMO_MODEL} 不可用")
    else:
        st.info("Model: Unknown / 状态未知")
    if ollama_status.detail:
        with st.expander("Status Details / 状态详情"):
            st.text(ollama_status.detail)

st.subheader("Try an Example / 载入示例")
example_name = st.selectbox("Example / 示例", tuple(DEMO_EXAMPLES))
if st.button("Load Example / 载入示例"):
    _load_example(example_name)
    st.rerun()

with st.form("qa_form"):
    mode_label = st.radio(
        "Run Mode / 运行模式",
        ("Hybrid QA / 混合式质检", "Rule Only / 仅规则质检"),
        horizontal=True,
    )
    source_col, target_col = st.columns(2)
    with source_col:
        source_zh = st.text_area(
            "Chinese Source / 中文原文 *", key="demo_source_zh", height=150
        )
    with target_col:
        target_ja = st.text_area(
            "Japanese Target / 日语译文 *", key="demo_target_ja", height=150
        )

    st.caption(
        "Context primarily helps semantic/pragmatic judgments such as keigo, "
        "first-person choice and character voice. / "
        "上下文主要帮助敬语、第一人称和角色语气等语义/语用判断。"
    )
    first, second, third = st.columns(3)
    with first:
        string_type = st.selectbox(
            "String Type / 文本类型",
            STRING_TYPE_OPTIONS,
            key="demo_string_type",
        )
        speaker = st.text_input("Speaker / 说话人", key="demo_speaker")
        addressee = st.text_input("Addressee / 对话对象", key="demo_addressee")
    with second:
        scene = st.text_input("Scene / 场景", key="demo_scene")
        relationship = st.text_input(
            "Relationship / 人物关系", key="demo_relationship"
        )
        max_length = st.text_input(
            "Max Length / 最大长度（可留空）", key="demo_max_length"
        )
    with third:
        context_before = st.text_area(
            "Context Before / 前文", key="demo_context_before", height=90
        )
        context_after = st.text_area(
            "Context After / 后文", key="demo_context_after", height=90
        )

    with st.expander("Optional Glossary Constraints / 可选术语约束"):
        st.caption(
            "Empty means no additional glossary constraints. / 留空表示不附加术语约束。"
        )
        glossary_frame = st.data_editor(
            pd.DataFrame(columns=REQUIRED_GLOSSARY_FIELDS),
            num_rows="dynamic",
            hide_index=True,
            key="demo_glossary",
            column_config={
                "source_term": "source_term / 中文术语",
                "approved_ja": "approved_ja / 核准日语",
                "forbidden_ja": "forbidden_ja / 禁用日语",
            },
        )

    submitted = st.form_submit_button("Run QA / 运行质检", type="primary")

if submitted:
    try:
        record = build_demo_record(
            source_zh=source_zh,
            target_ja=target_ja,
            string_type=string_type,
            speaker=speaker,
            addressee=addressee,
            scene=scene,
            relationship=relationship,
            context_before=context_before,
            context_after=context_after,
            max_length=max_length,
        )
        glossary = prepare_glossary(glossary_frame)
        if mode_label.startswith("Rule Only"):
            result = run_rule_only(record, glossary)
            _display_result(result)
        elif ollama_status.service != "available" or ollama_status.model != "available":
            st.error(
                "Ollama is not available. / Ollama 当前不可用。\n\n"
                "Start Ollama and make sure qwen3.5:9b is installed. / "
                "请启动 Ollama，并确认已安装 qwen3.5:9b。"
            )
        else:
            with st.spinner("Running frozen Hybrid QA / 正在运行冻结的混合质检……"):
                result = run_hybrid_qa(record, glossary)
            _display_result(result)
    except DemoInputError as exc:
        st.error(str(exc))
    except DemoProviderFailure as exc:
        st.error(
            "Ollama request failed. / Ollama 请求失败。请确认服务和模型可用后重试。"
        )
        with st.expander("Technical Details / 技术详情"):
            st.text(f"category={exc.category}\n{exc}")
    except Exception as exc:  # Last-resort UI boundary; no traceback is shown.
        st.error("QA run failed. / 质检运行失败。")
        with st.expander("Technical Details / 技术详情"):
            st.text(f"{type(exc).__name__}: {exc}")

with st.expander("How It Works / 工作原理"):
    st.code(
        "Source / Target / Context\n"
        "          ↓\n"
        "Rule QA        LLM QA\n"
        "          ↓\n"
        "Hybrid Routing\n"
        "          ↓\n"
        "Unified Issues"
    )

with st.expander("Project Info / 项目信息"):
    st.write(
        "Historical frozen benchmark result / 历史冻结评测结果："
        "Hybrid Prompt v2.1 F1 = 0.7030"
    )
    st.caption(
        "60-item original synthetic held-out test set; not production accuracy. / "
        "60 条原创 synthetic 独立留出测试集；不是生产准确率。"
    )
