import unittest

from j_gamelqa.rules.number import check_number_issues, extract_numbers


def make_record(source, target):
    return {"string_id": "TEST", "source_zh": source, "target_ja": target}


class NumberCheckerTests(unittest.TestCase):
    def test_matching_numbers(self):
        self.assertEqual(check_number_issues(make_record("获得10金币", "金貨を10枚獲得")), [])

    def test_number_mismatch(self):
        issues = check_number_issues(make_record("3分钟后关闭", "5分後に閉じる"))
        self.assertEqual(issues[0].issue_type, "number_mismatch")
        self.assertEqual(issues[0].evidence["missing"], ["3"])
        self.assertEqual(issues[0].evidence["extra"], ["5"])

    def test_number_missing_and_extra(self):
        missing = check_number_issues(make_record("恢复25%生命", "生命を回復"))
        extra = check_number_issues(make_record("生命恢复", "生命を25%回復"))
        self.assertEqual(missing[0].issue_type, "number_missing")
        self.assertEqual(extra[0].issue_type, "number_extra")

    def test_decimals_percentages_and_placeholder_digits(self):
        self.assertEqual(extract_numbers("提高1.5%，保留{item2_count}"), ["1.5%"])
