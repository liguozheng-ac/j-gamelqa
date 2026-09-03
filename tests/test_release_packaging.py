import unittest
import re
from pathlib import Path

from j_gamelqa.io import load_dev_dataset, load_glossary
from j_gamelqa.release import (
    EXPECTED_HELDOUT_COMPARISON_SHA256,
    EXPECTED_PROMPT_SHA256,
    EXPECTED_TEST_SHA256,
    build_release_manifest,
    sha256_file,
)
from j_gamelqa.rule_engine import evaluate_dataframe


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ReleasePackagingTests(unittest.TestCase):
    def test_readme_exposes_release_story_and_limit(self):
        readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        for heading in (
            "## Problem",
            "## Core Idea",
            "## Architecture",
            "## Held-out Results",
            "## Why Context Matters",
            "## Important Limitations",
            "## Quickstart",
        ):
            self.assertIn(heading, readme)
        self.assertIn("F1 = 0.7030", readme)
        self.assertIn("误报 8 条", readme)
        self.assertIn("已冻结并退役", readme)

    def test_demo_is_answer_free_and_runs_only_rule_pipeline(self):
        frame = load_dev_dataset(PROJECT_ROOT / "examples" / "example_input.csv")
        glossary = load_glossary(
            PROJECT_ROOT / "examples" / "example_glossary.csv"
        )
        issues = evaluate_dataframe(frame, glossary)
        keys = {(issue.string_id, issue.issue_type) for issue in issues}
        self.assertEqual(
            keys,
            {
                ("DEMO_002", "placeholder_missing"),
                ("DEMO_003", "terminology_forbidden"),
            },
        )

    def test_release_manifest_builder_verifies_frozen_inputs(self):
        manifest = build_release_manifest(
            PROJECT_ROOT,
            automated_test_count=188,
            demo_smoke_inference_calls=1,
        )
        self.assertEqual(manifest["version"], "1.0.0")
        self.assertEqual(manifest["prompt_sha256"], EXPECTED_PROMPT_SHA256)
        self.assertEqual(manifest["test_sha256"], EXPECTED_TEST_SHA256)
        self.assertEqual(
            manifest["heldout_result_artifact_sha256"],
            EXPECTED_HELDOUT_COMPARISON_SHA256,
        )
        self.assertEqual(manifest["heldout_result"]["tp"], 58)
        self.assertEqual(manifest["counts"]["held_out_test_sample_count"], 60)
        self.assertEqual(manifest["counts"]["automated_unittest_count"], 188)
        self.assertEqual(manifest["pyproject_sha256"], sha256_file(PROJECT_ROOT / "pyproject.toml"))
        self.assertEqual(
            manifest["demo"],
            {
                "available": True,
                "framework": "Streamlit",
                "entry_point": "j-gamelqa-demo",
                "optional_dependency": "streamlit>=1.63,<2",
                "smoke_inference_calls": 1,
            },
        )

    def test_public_markdown_has_no_absolute_windows_path(self):
        findings = []
        for path in PROJECT_ROOT.rglob("*.md"):
            if any(part in {".git", ".venv"} for part in path.parts):
                continue
            text = path.read_text(encoding="utf-8")
            if re.search(r"[A-Za-z]:\\", text):
                findings.append(str(path.relative_to(PROJECT_ROOT)))
        self.assertEqual(findings, [])

    def test_public_portfolio_documents_and_svg_assets_exist(self):
        required = (
            "docs/public_release_audit.md",
            "docs/portfolio_onepager.md",
            "docs/resume_cn.md",
            "docs/job_talk_tracks.md",
            "docs/github_release_checklist.md",
            "docs/assets/j-gamelqa-architecture.svg",
            "docs/assets/j-gamelqa-experiment-flow.svg",
        )
        for relative_path in required:
            path = PROJECT_ROOT / relative_path
            self.assertTrue(path.is_file(), relative_path)
            self.assertGreater(path.stat().st_size, 0, relative_path)


if __name__ == "__main__":
    unittest.main()
