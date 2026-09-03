import unittest

from j_gamelqa.rules.markup import check_markup_issues, extract_markup


def make_record(source, target):
    return {"string_id": "TEST", "source_zh": source, "target_ja": target}


class MarkupCheckerTests(unittest.TestCase):
    def test_matching_markup(self):
        record = make_record("按下<b>F1</b>", "<b>F1</b>を押す")
        self.assertEqual(check_markup_issues(record), [])

    def test_missing_markup(self):
        issues = check_markup_issues(make_record("按下<b>F1</b>", "<b>F1を押す"))
        self.assertEqual(issues[0].issue_type, "markup_missing")
        self.assertEqual(issues[0].evidence["missing"], ["</b>"])

    def test_modified_markup(self):
        issues = check_markup_issues(
            make_record("<color=red>危险</color>", "<color=blue>危険</color>")
        )
        self.assertEqual(issues[0].issue_type, "markup_modified")

    def test_malformed_markup(self):
        issues = check_markup_issues(make_record("<b>危险</b>", "<b危険</b>"))
        self.assertEqual(issues[0].issue_type, "markup_malformed")

    def test_extract_common_game_tags(self):
        self.assertEqual(
            extract_markup("<color=red><b>危险</b></color>"),
            ["<color=red>", "<b>", "</b>", "</color>"],
        )
