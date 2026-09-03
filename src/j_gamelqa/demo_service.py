"""Thin single-record adapter for the optional local Streamlit demo.

This module deliberately delegates all QA decisions to the existing rule engine,
Prompt v2.1 builder, strict parser, Ollama provider, and hybrid merge policy.
"""

from dataclasses import dataclass, field
import json
import socket
from typing import Any
import urllib.error
import urllib.request

from j_gamelqa.hybrid import merge_hybrid_predictions
from j_gamelqa.io import REQUIRED_GLOSSARY_FIELDS
from j_gamelqa.llm_evaluator import LLMProtocolDiagnostics, parse_llm_response
from j_gamelqa.models import Issue
from j_gamelqa.prompts import LLMInputMode
from j_gamelqa.prompts_v21 import build_evaluator_prompt_v21
from j_gamelqa.providers.ollama import OllamaProvider, OllamaProviderError
from j_gamelqa.rule_engine import evaluate_record
from j_gamelqa.taxonomy import REGISTERED_ISSUE_TYPES


DEMO_MODEL = "qwen3.5:9b"
DEMO_ENDPOINT = "http://127.0.0.1:11434/api/generate"
DEMO_STRING_ID = "DEMO_INPUT"

# Values observed in the existing development input schema. The demo does not
# read a benchmark at runtime.
STRING_TYPE_OPTIONS = (
    "dialogue",
    "npc_dialogue",
    "battle_ui",
    "item_description",
    "menu_ui",
    "narration",
    "notification",
    "quest",
    "quest_objective",
    "skill_description",
    "system_message",
    "system_warning",
    "tutorial",
)

# Presentation-only labels. The canonical taxonomy remains in taxonomy.py.
ISSUE_TYPE_LABELS_ZH = {
    "placeholder_missing": "占位符缺失",
    "placeholder_modified": "占位符被修改",
    "placeholder_extra": "占位符多余",
    "number_mismatch": "数字不匹配",
    "number_missing": "数字缺失",
    "number_extra": "数字多余",
    "markup_malformed": "标记格式损坏",
    "markup_modified": "标记被修改",
    "markup_missing": "标记缺失",
    "markup_extra": "标记多余",
    "markup_order_mismatch": "标记顺序不匹配",
    "linebreak_mismatch": "换行不匹配",
    "length_overflow": "长度超限",
    "terminology_forbidden": "使用禁用术语",
    "terminology_not_approved": "未使用核准术语",
    "omission": "漏译",
    "addition": "增译",
    "mistranslation": "误译",
    "translationese": "翻译腔",
    "keigo_mismatch": "敬语不匹配",
    "first_person_mismatch": "第一人称不匹配",
    "character_voice_mismatch": "角色语气不匹配",
}

if set(ISSUE_TYPE_LABELS_ZH) != REGISTERED_ISSUE_TYPES:
    raise RuntimeError("Demo labels must cover the canonical issue taxonomy exactly.")


DEMO_EXAMPLES: dict[str, dict[str, object]] = {
    "A · Placeholder missing / 占位符缺失": {
        "source_zh": "获得 {item_count} 枚星砂。",
        "target_ja": "星砂を獲得しました。",
        "string_type": "notification",
        "speaker": "",
        "addressee": "",
        "scene": "reward popup",
        "relationship": "",
        "context_before": "",
        "context_after": "",
        "max_length": "",
    },
    "B · Context-sensitive keigo / 上下文敬语": {
        "source_zh": "陛下，北门的守卫已经部署完毕。",
        "target_ja": "王よ、北門の守りはもう配置したぞ。",
        "string_type": "dialogue",
        "speaker": "王宫侍从",
        "addressee": "国王",
        "scene": "朝会报告",
        "relationship": "臣下 → 君主；正式公开场合",
        "context_before": "侍从在群臣面前向国王报告城防。",
        "context_after": "国王点头，命令继续戒备。",
        "max_length": "",
    },
    "C · Clean / 正常译文": {
        "source_zh": "护盾还剩 30%，先退到石柱后面！",
        "target_ja": "シールドはあと30％だ。いったん石柱の陰へ下がれ！",
        "string_type": "dialogue",
        "speaker": "队长莱因",
        "addressee": "新兵小队",
        "scene": "遗迹防卫战",
        "relationship": "经验丰富的队长 → 信任的新兵",
        "context_before": "莱因一直用简短直接的命令指挥队伍。",
        "context_after": "队员们立刻寻找掩体。",
        "max_length": "",
    },
}


class DemoInputError(ValueError):
    """A user-correctable input error."""


class DemoProviderFailure(RuntimeError):
    """A friendly wrapper around an Ollama infrastructure failure."""

    def __init__(self, category: str, message: str):
        super().__init__(message)
        self.category = category


@dataclass(frozen=True, slots=True)
class OllamaStatus:
    service: str
    model: str
    detail: str = ""


@dataclass(slots=True)
class DemoRunResult:
    mode: str
    rule_issues: list[Issue]
    llm_issues: list[Issue]
    hybrid_issues: list[Issue]
    raw_llm_response: str | None = None
    prompt: str | None = None
    protocol_success: bool | None = None
    protocol_diagnostics: dict[str, object] = field(default_factory=dict)
    latency_seconds: float | None = None
    excluded_llm_issues: list[Issue] = field(default_factory=list)
    duplicate_predictions: list[dict[str, object]] = field(default_factory=list)


def build_demo_record(
    *,
    source_zh: str,
    target_ja: str,
    string_type: str = "dialogue",
    speaker: str = "",
    addressee: str = "",
    scene: str = "",
    relationship: str = "",
    context_before: str = "",
    context_after: str = "",
    max_length: object = None,
) -> dict[str, object]:
    """Validate UI input and adapt it to the existing record contract."""
    if not isinstance(source_zh, str) or not source_zh.strip():
        raise DemoInputError("Chinese Source / 中文原文不能为空。")
    if not isinstance(target_ja, str) or not target_ja.strip():
        raise DemoInputError("Japanese Target / 日语译文不能为空。")
    if string_type not in STRING_TYPE_OPTIONS:
        raise DemoInputError(f"Unsupported String Type / 不支持的文本类型：{string_type}")

    parsed_max_length: int | None
    if max_length is None or (isinstance(max_length, str) and not max_length.strip()):
        parsed_max_length = None
    else:
        try:
            parsed_max_length = int(max_length)
        except (TypeError, ValueError) as exc:
            raise DemoInputError("Max Length / 最大长度必须是正整数或留空。") from exc
        if parsed_max_length <= 0:
            raise DemoInputError("Max Length / 最大长度必须是正整数或留空。")

    return {
        "string_id": DEMO_STRING_ID,
        "source_zh": source_zh,
        "target_ja": target_ja,
        "string_type": string_type,
        "speaker": speaker,
        "addressee": addressee,
        "scene": scene,
        "relationship": relationship,
        "context_before": context_before,
        "context_after": context_after,
        "max_length": parsed_max_length,
    }


def prepare_glossary(rows: object) -> list[dict[str, str]]:
    """Validate editor rows against the existing glossary schema."""
    if rows is None:
        return []
    if hasattr(rows, "to_dict"):
        rows = rows.to_dict(orient="records")
    if not isinstance(rows, list):
        raise DemoInputError("Glossary / 术语表必须是表格记录。")

    prepared: list[dict[str, str]] = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise DemoInputError(f"Glossary row {index} / 术语表第 {index} 行格式无效。")
        values = {
            field_name: str(row.get(field_name, "") or "").strip()
            for field_name in REQUIRED_GLOSSARY_FIELDS
        }
        if not any(values.values()):
            continue
        if not values["source_term"] or not values["approved_ja"]:
            raise DemoInputError(
                f"Glossary row {index}: source_term 和 approved_ja 不能为空。"
            )
        prepared.append(values)
    return prepared


def run_rule_only(
    record: dict[str, object], glossary: list[dict[str, str]]
) -> DemoRunResult:
    """Run the unchanged rule engine for one record."""
    rule_issues = evaluate_record(record, glossary)
    return DemoRunResult(
        mode="rule_only",
        rule_issues=rule_issues,
        llm_issues=[],
        hybrid_issues=list(rule_issues),
    )


def run_hybrid_qa(
    record: dict[str, object],
    glossary: list[dict[str, str]],
    *,
    provider: OllamaProvider | None = None,
) -> DemoRunResult:
    """Run frozen Rule + Prompt v2.1 WITH_CONTEXT + strict Hybrid flow once."""
    rule_issues = evaluate_record(record, glossary)
    prompt = build_evaluator_prompt_v21(
        record,
        glossary,
        LLMInputMode.WITH_CONTEXT,
    )
    provider = provider or OllamaProvider(
        DEMO_MODEL,
        endpoint=DEMO_ENDPOINT,
        timeout_seconds=120.0,
        temperature=0.0,
        thinking=False,
        stream=False,
    )
    try:
        generation = provider.generate(prompt)
    except OllamaProviderError as exc:
        raise DemoProviderFailure(exc.category, str(exc)) from exc

    parsed = parse_llm_response(generation.raw_response, str(record["string_id"]))
    hybrid = merge_hybrid_predictions(rule_issues, parsed.predictions)
    return DemoRunResult(
        mode="hybrid",
        rule_issues=rule_issues,
        llm_issues=parsed.predictions,
        hybrid_issues=hybrid.predictions,
        raw_llm_response=generation.raw_response,
        prompt=prompt,
        protocol_success=parsed.is_valid,
        protocol_diagnostics=parsed.diagnostics.to_dict(),
        latency_seconds=generation.latency_seconds,
        excluded_llm_issues=hybrid.llm_predictions_excluded_from_hybrid,
        duplicate_predictions=hybrid.duplicate_predictions,
    )


def _tags_endpoint(generate_endpoint: str) -> str:
    suffix = "/api/generate"
    if generate_endpoint.endswith(suffix):
        return generate_endpoint[: -len(suffix)] + "/api/tags"
    return generate_endpoint.rstrip("/") + "/api/tags"


def check_ollama_status(
    *,
    model: str = DEMO_MODEL,
    endpoint: str = DEMO_ENDPOINT,
    timeout_seconds: float = 2.0,
) -> OllamaStatus:
    """Check Ollama's model list without invoking model generation."""
    request = urllib.request.Request(_tags_endpoint(endpoint), method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return OllamaStatus("unavailable", "unknown", f"HTTP {exc.code}")
    except urllib.error.URLError as exc:
        detail = "timeout" if isinstance(exc.reason, (TimeoutError, socket.timeout)) else str(exc.reason)
        return OllamaStatus("unavailable", "unknown", detail)
    except (OSError, TimeoutError, socket.timeout) as exc:
        return OllamaStatus("unavailable", "unknown", str(exc))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        return OllamaStatus("available", "unknown", "Invalid model-list response")

    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        return OllamaStatus("available", "unknown", "Model list is unavailable")
    names = {
        value
        for item in models
        if isinstance(item, dict)
        for value in (item.get("name"), item.get("model"))
        if isinstance(value, str)
    }
    return OllamaStatus(
        "available",
        "available" if model in names else "unavailable",
        "",
    )
