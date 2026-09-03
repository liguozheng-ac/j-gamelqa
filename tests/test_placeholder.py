import csv
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from j_gamelqa.rules.placeholder import (  # noqa: E402
    check_placeholder_issue,
    compare_placeholders,
    extract_placeholders,
)


class PlaceholderCheckerTests(unittest.TestCase):
    def test_no_placeholder(self):
        result = check_placeholder_issue("任务完成。", "任務完了。")

        self.assertEqual(result["issue_type"], "none")
        self.assertFalse(result["has_issue"])

    def test_correctly_preserved_placeholder(self):
        result = check_placeholder_issue(
            "勇者{player_name}，欢迎回来！",
            "勇者{player_name}、お帰りなさい！",
        )

        self.assertEqual(result["issue_type"], "none")

    def test_missing_placeholder(self):
        result = check_placeholder_issue(
            "勇者{player_name}，欢迎回来！",
            "勇者様、お帰りなさい！",
        )

        self.assertEqual(result["issue_type"], "placeholder_missing")
        self.assertEqual(result["missing"], ["{player_name}"])
        self.assertEqual(result["extra"], [])

    def test_modified_placeholder(self):
        result = check_placeholder_issue(
            "获得{item_count}枚金币。",
            "{item_num}枚の金貨を獲得しました。",
        )

        self.assertEqual(result["issue_type"], "placeholder_modified")
        self.assertEqual(result["missing"], ["{item_count}"])
        self.assertEqual(result["extra"], ["{item_num}"])

    def test_extra_placeholder(self):
        result = check_placeholder_issue(
            "任务完成。",
            "{player_name}、任務完了です。",
        )

        self.assertEqual(result["issue_type"], "placeholder_extra")
        self.assertEqual(result["extra"], ["{player_name}"])

    def test_multiple_placeholders_can_be_reordered(self):
        result = compare_placeholders(
            "Health: %(current)d/%(maximum)d HP",
            "最大HP %(maximum)d、現在HP %(current)d",
        )

        self.assertEqual(result, {"missing": [], "extra": []})

    def test_brace_placeholder_format(self):
        self.assertEqual(
            extract_placeholders("你好，{player_name}！"),
            ["{player_name}"],
        )

    def test_python_string_placeholder_format(self):
        self.assertEqual(
            extract_placeholders("Welcome, %(player)s!"),
            ["%(player)s"],
        )

    def test_python_number_placeholder_format(self):
        self.assertEqual(
            extract_placeholders("HP: %(current)d/%(maximum)d"),
            ["%(current)d", "%(maximum)d"],
        )

    def test_duplicate_placeholder_count_is_checked(self):
        result = check_placeholder_issue(
            "{item_count} + {item_count}",
            "{item_count}",
        )

        self.assertEqual(result["issue_type"], "placeholder_missing")
        self.assertEqual(result["missing"], ["{item_count}"])

    def test_pilot_dataset_predictions(self):
        expected_predictions = {
            "PILOT_001": "none",
            "PILOT_002": "placeholder_missing",
            "PILOT_003": "placeholder_modified",
            "PILOT_004": "none",
            "PILOT_005": "none",
            "PILOT_006": "none",
            "PILOT_007": "none",
            "PILOT_008": "none",
            "PILOT_009": "none",
            "PILOT_010": "none",
        }

        with (PROJECT_ROOT / "data" / "pilot.csv").open(
            encoding="utf-8", newline=""
        ) as file:
            rows = csv.DictReader(file)
            actual_predictions = {
                row["string_id"]: check_placeholder_issue(
                    row["source_zh"], row["target_ja"]
                )["issue_type"]
                for row in rows
            }

        self.assertEqual(actual_predictions, expected_predictions)


if __name__ == "__main__":
    unittest.main()
