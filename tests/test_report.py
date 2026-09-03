import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from j_gamelqa.models import Issue
from j_gamelqa.report import write_reports


class ReportTests(unittest.TestCase):
    def test_three_report_formats_are_written(self):
        issue = Issue(
            string_id="TEST",
            checker="number",
            issue_type="number_mismatch",
            severity="major",
            message="数字不一致。",
            evidence={"missing": ["3"], "extra": ["5"]},
        )

        with tempfile.TemporaryDirectory() as directory:
            paths = write_reports([issue], directory)
            self.assertTrue(all(path.exists() for path in paths.values()))
            payload = json.loads(paths["json"].read_text(encoding="utf-8"))
            csv_frame = pd.read_csv(paths["csv"])
            excel_frame = pd.read_excel(paths["xlsx"])
            self.assertEqual(payload[0]["issue_type"], "number_mismatch")
            self.assertEqual(csv_frame.loc[0, "checker"], "number")
            self.assertEqual(excel_frame.loc[0, "severity"], "major")
