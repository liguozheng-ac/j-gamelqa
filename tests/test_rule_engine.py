import unittest

import pandas as pd

from j_gamelqa.rule_engine import evaluate_dataframe, evaluate_record


def make_record():
    return {
        "string_id": "TEST",
        "source_zh": "勇者{name}，3分钟后出发",
        "target_ja": "勇者{player}、5分後に出発",
        "string_type": "dialogue",
        "speaker": "系统",
        "addressee": "玩家",
        "scene": "测试",
        "relationship": "系统通知",
        "context_before": "",
        "context_after": "",
        "max_length": "100",
    }


class RuleEngineTests(unittest.TestCase):
    def test_one_record_can_return_multiple_issues(self):
        issues = evaluate_record(make_record(), [])
        self.assertEqual(
            [(issue.checker, issue.issue_type) for issue in issues],
            [
                ("placeholder", "placeholder_modified"),
                ("number", "number_mismatch"),
            ],
        )

    def test_expected_labels_are_not_prediction_fields(self):
        record = make_record()
        record["expected_issue"] = "none"
        record["expected_severity"] = "none"
        frame = pd.DataFrame([record])
        issues = evaluate_dataframe(frame, [])
        self.assertEqual(len(issues), 2)
