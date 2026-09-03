import unittest

from j_gamelqa.rules.length import check_length_issues


def make_record(target, max_length):
    return {
        "string_id": "TEST",
        "source_zh": "测试",
        "target_ja": target,
        "max_length": max_length,
    }


class LengthCheckerTests(unittest.TestCase):
    def test_at_limit_is_valid(self):
        self.assertEqual(check_length_issues(make_record("12345", "5")), [])

    def test_over_limit(self):
        issues = check_length_issues(make_record("123456", "5"))
        self.assertEqual(issues[0].issue_type, "length_overflow")
        self.assertEqual(issues[0].evidence["overflow"], 1)

    def test_blank_limit_is_skipped(self):
        self.assertEqual(check_length_issues(make_record("任意の長さ", "")), [])

    def test_invalid_limit_is_explicit_error(self):
        with self.assertRaises(ValueError):
            check_length_issues(make_record("text", "five"))
