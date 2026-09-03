import inspect
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import j_gamelqa.demo_service as demo_service
from j_gamelqa.demo_service import (
    DEMO_EXAMPLES,
    ISSUE_TYPE_LABELS_ZH,
    DemoInputError,
    build_demo_record,
    prepare_glossary,
    run_hybrid_qa,
    run_rule_only,
)
from j_gamelqa.hybrid import merge_hybrid_predictions
from j_gamelqa.taxonomy import REGISTERED_ISSUE_TYPES


class FakeProvider:
    def __init__(self, raw_response):
        self.raw_response = raw_response
        self.calls = 0

    def generate(self, prompt):
        self.calls += 1
        return SimpleNamespace(
            raw_response=self.raw_response,
            latency_seconds=0.01,
        )


class DemoServiceTests(unittest.TestCase):
    def test_rule_only_handles_one_record_with_existing_engine(self):
        record = build_demo_record(**DEMO_EXAMPLES[next(iter(DEMO_EXAMPLES))])
        result = run_rule_only(record, [])
        self.assertEqual(result.mode, "rule_only")
        self.assertEqual(
            [issue.issue_type for issue in result.rule_issues],
            ["placeholder_missing"],
        )
        self.assertEqual(result.hybrid_issues, result.rule_issues)
        self.assertEqual(result.llm_issues, [])

    def test_demo_service_does_not_read_heldout_or_annotation_files(self):
        source = inspect.getsource(demo_service).lower()
        for forbidden in (
            "test.csv",
            "test_annotations",
            "dev_annotations",
            "load_test",
        ):
            self.assertNotIn(forbidden, source)
        record = build_demo_record(
            source_zh="返回大厅。",
            target_ja="ロビーに戻る。",
            string_type="menu_ui",
        )
        with patch("builtins.open", side_effect=AssertionError("unexpected file read")):
            result = run_rule_only(record, [])
        self.assertEqual(result.rule_issues, [])

    def test_hybrid_uses_existing_prompt_parser_and_merge_policy_once(self):
        record = build_demo_record(
            source_zh="请您过目。",
            target_ja="見てくれ。",
            speaker="副官",
            addressee="司令官",
            relationship="部下 → 上司",
        )
        provider = FakeProvider(
            json.dumps(
                {
                    "string_id": "DEMO_INPUT",
                    "issues": [
                        {
                            "issue_type": "keigo_mismatch",
                            "severity": "major",
                            "source_span": "请您过目",
                            "target_span": "見てくれ",
                            "evidence": "A subordinate uses a casual command to a commander.",
                        }
                    ],
                },
                ensure_ascii=False,
            )
        )
        with patch.object(
            demo_service,
            "merge_hybrid_predictions",
            wraps=merge_hybrid_predictions,
        ) as merge_mock:
            result = run_hybrid_qa(record, [], provider=provider)
        self.assertEqual(provider.calls, 1)
        merge_mock.assert_called_once()
        self.assertTrue(result.protocol_success)
        self.assertEqual(
            [issue.issue_type for issue in result.hybrid_issues],
            ["keigo_mismatch"],
        )
        self.assertIn("Minimal evaluation guidance", result.prompt)

    def test_protocol_failure_is_preserved_without_retry_or_repair(self):
        record = build_demo_record(source_zh="继续。", target_ja="続ける。")
        provider = FakeProvider("```json\n{}\n```")
        result = run_hybrid_qa(record, [], provider=provider)
        self.assertEqual(provider.calls, 1)
        self.assertFalse(result.protocol_success)
        self.assertEqual(result.raw_llm_response, "```json\n{}\n```")
        self.assertTrue(result.protocol_diagnostics["parse_failures"])

    def test_empty_required_text_and_invalid_max_length_are_rejected(self):
        with self.assertRaisesRegex(DemoInputError, "中文原文不能为空"):
            build_demo_record(source_zh=" ", target_ja="有効")
        with self.assertRaisesRegex(DemoInputError, "日语译文不能为空"):
            build_demo_record(source_zh="有效", target_ja=" ")
        with self.assertRaisesRegex(DemoInputError, "最大长度必须是正整数"):
            build_demo_record(source_zh="有效", target_ja="有効", max_length="abc")

    def test_optional_glossary_uses_existing_schema(self):
        rows = [
            {
                "source_term": "星砂",
                "approved_ja": "星砂",
                "forbidden_ja": "スターダスト",
            },
            {"source_term": "", "approved_ja": "", "forbidden_ja": ""},
        ]
        self.assertEqual(prepare_glossary(rows), [rows[0]])
        with self.assertRaises(DemoInputError):
            prepare_glossary([{"source_term": "星砂", "approved_ja": ""}])

    def test_chinese_labels_cover_canonical_taxonomy_without_changing_it(self):
        before = frozenset(REGISTERED_ISSUE_TYPES)
        self.assertEqual(set(ISSUE_TYPE_LABELS_ZH), REGISTERED_ISSUE_TYPES)
        self.assertEqual(REGISTERED_ISSUE_TYPES, before)


if __name__ == "__main__":
    unittest.main()
