import unittest

from j_gamelqa.rules.linebreak import check_linebreak_issues, count_linebreaks


def make_record(source, target):
    return {"string_id": "TEST", "source_zh": source, "target_ja": target}


class LinebreakCheckerTests(unittest.TestCase):
    def test_matching_real_linebreaks(self):
        self.assertEqual(check_linebreak_issues(make_record("第一行\n第二行", "一行目\n二行目")), [])

    def test_missing_real_linebreak(self):
        issues = check_linebreak_issues(make_record("第一行\n第二行", "一行目、二行目"))
        self.assertEqual(issues[0].issue_type, "linebreak_mismatch")

    def test_literal_backslash_n_is_counted_separately(self):
        self.assertEqual(
            count_linebreaks(r"第一行\n第二行"),
            {"actual_newlines": 0, "escaped_newlines": 1},
        )
