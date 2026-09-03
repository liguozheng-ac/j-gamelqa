import unittest

from j_gamelqa.rules.terminology import check_terminology_issues


GLOSSARY = [
    {"source_term": "星辉石", "approved_ja": "星輝石", "forbidden_ja": "スター石"}
]


def make_record(source, target):
    return {"string_id": "TEST", "source_zh": source, "target_ja": target}


class TerminologyCheckerTests(unittest.TestCase):
    def test_approved_term(self):
        self.assertEqual(
            check_terminology_issues(make_record("获得星辉石", "星輝石を獲得"), GLOSSARY),
            [],
        )

    def test_forbidden_term(self):
        issues = check_terminology_issues(
            make_record("获得星辉石", "スター石を獲得"), GLOSSARY
        )
        self.assertEqual(issues[0].issue_type, "terminology_forbidden")

    def test_approved_term_missing(self):
        issues = check_terminology_issues(
            make_record("获得星辉石", "特殊な鉱石を獲得"), GLOSSARY
        )
        self.assertEqual(issues[0].issue_type, "terminology_not_approved")

    def test_source_term_absent(self):
        self.assertEqual(
            check_terminology_issues(make_record("获得金币", "金貨を獲得"), GLOSSARY),
            [],
        )
