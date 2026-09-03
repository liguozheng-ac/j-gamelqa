import unittest

from j_gamelqa.prompts import (
    CONTEXT_INPUT_FIELDS,
    LLMInputMode,
    build_evaluator_prompt,
    build_llm_input,
)
from j_gamelqa.taxonomy import ISSUE_TYPE_DEFINITIONS, REGISTERED_ISSUE_TYPES


GLOSSARY = [
    {
        "source_term": "传送门",
        "approved_ja": "転送門",
        "forbidden_ja": "ポータル|ゲート",
    },
    {
        "source_term": "金币",
        "approved_ja": "金貨",
        "forbidden_ja": "コイン",
    },
]


def make_record():
    return {
        "string_id": "DEV_TEST",
        "source_zh": "传送门将在这里开启。",
        "target_ja": "転送門はここに開きます。",
        "string_type": "dialogue",
        "speaker": "引路法师",
        "addressee": "玩家",
        "scene": "浮空塔",
        "relationship": "法师向同行者说明路线",
        "context_before": "法阵已经亮起。",
        "context_after": "队伍准备离开。",
        "max_length": "80",
    }


class PromptBuilderTests(unittest.TestCase):
    def test_without_context_excludes_context_fields(self):
        payload = build_llm_input(
            make_record(), GLOSSARY, LLMInputMode.WITHOUT_CONTEXT
        )
        prompt = build_evaluator_prompt(
            make_record(), GLOSSARY, LLMInputMode.WITHOUT_CONTEXT
        )
        for field in CONTEXT_INPUT_FIELDS:
            self.assertNotIn(field, payload)
            self.assertNotIn(f'"{field}"', prompt)

    def test_with_context_includes_context_fields(self):
        record = make_record()
        payload = build_llm_input(record, GLOSSARY, LLMInputMode.WITH_CONTEXT)
        for field in CONTEXT_INPUT_FIELDS:
            self.assertEqual(payload[field], record[field])

    def test_modes_keep_all_non_context_input_identical(self):
        without_context = build_llm_input(
            make_record(), GLOSSARY, LLMInputMode.WITHOUT_CONTEXT
        )
        with_context = build_llm_input(
            make_record(), GLOSSARY, LLMInputMode.WITH_CONTEXT
        )
        for field, value in without_context.items():
            self.assertEqual(with_context[field], value)

    def test_glossary_constraints_are_identical_between_modes(self):
        without_context = build_llm_input(
            make_record(), GLOSSARY, LLMInputMode.WITHOUT_CONTEXT
        )
        with_context = build_llm_input(
            make_record(), GLOSSARY, LLMInputMode.WITH_CONTEXT
        )
        expected = [
            {
                "source_term": "传送门",
                "approved_ja": "転送門",
                "forbidden_ja": ["ポータル", "ゲート"],
            }
        ]
        self.assertEqual(
            without_context["applicable_glossary_constraints"], expected
        )
        self.assertEqual(
            with_context["applicable_glossary_constraints"], expected
        )

    def test_prompt_contains_every_registered_type_and_definition(self):
        prompt = build_evaluator_prompt(
            make_record(), GLOSSARY, LLMInputMode.WITHOUT_CONTEXT
        )
        for issue_type in REGISTERED_ISSUE_TYPES:
            self.assertIn(f"- {issue_type}:", prompt)
            self.assertIn(ISSUE_TYPE_DEFINITIONS[issue_type], prompt)

    def test_prompt_allows_clean_and_multiple_issues(self):
        prompt = build_evaluator_prompt(
            make_record(), GLOSSARY, LLMInputMode.WITHOUT_CONTEXT
        )
        self.assertIn("empty issues list", prompt)
        self.assertIn("multiple different issue types", prompt)
        self.assertIn("Return JSON only", prompt)
