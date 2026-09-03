import unittest

from j_gamelqa.hybrid import merge_hybrid_predictions
from j_gamelqa.models import Issue
from j_gamelqa.prompt_v21_analysis import (
    FOCUS_ISSUE_TYPES,
    analysis_artifact_paths,
)


def issue(string_id, issue_type, checker="japanese_llm"):
    return Issue(
        string_id=string_id,
        checker=checker,
        issue_type=issue_type,
        severity="major",
        message="test",
    )


class PromptV21AnalysisTests(unittest.TestCase):
    def test_analysis_artifacts_do_not_overlap_v1_or_v2(self):
        paths = set(analysis_artifact_paths("outputs").values())
        names = {path.name for path in paths}
        self.assertNotIn("qwen35_9b_with_context_evaluation.json", names)
        self.assertNotIn(
            "qwen35_9b_with_context_prompt_v2_dev_evaluation.json", names
        )
        self.assertIn("prompt_v1_v2_v21_dev_comparison.json", names)
        self.assertIn("prompt_v21_dev_candidate_gate.json", names)

    def test_hybrid_policy_still_uses_rules_for_technical_types(self):
        rules = [issue("S1", "number_missing", "number")]
        llm = [
            issue("S2", "translationese"),
            issue("S3", "placeholder_missing"),
        ]
        merged = merge_hybrid_predictions(rules, llm)
        self.assertEqual(
            [(item.string_id, item.issue_type) for item in merged.predictions],
            [("S1", "number_missing"), ("S2", "translationese")],
        )
        self.assertEqual(
            merged.llm_predictions_excluded_from_hybrid[0].issue_type,
            "placeholder_missing",
        )

    def test_focus_types_are_predefined(self):
        self.assertEqual(
            FOCUS_ISSUE_TYPES,
            (
                "mistranslation",
                "translationese",
                "keigo_mismatch",
                "first_person_mismatch",
                "character_voice_mismatch",
            ),
        )


if __name__ == "__main__":
    unittest.main()
