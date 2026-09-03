from io import StringIO
from pathlib import Path
import sys
import tomllib
import unittest
from unittest.mock import patch

from j_gamelqa import demo_cli
from j_gamelqa.demo_service import DEMO_EXAMPLES, check_ollama_status


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FakeHTTPResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self.body


class DemoPackagingTests(unittest.TestCase):
    def test_demo_optional_dependency_and_cli_entry_point_exist(self):
        with (PROJECT_ROOT / "pyproject.toml").open("rb") as handle:
            project = tomllib.load(handle)["project"]
        self.assertIn("streamlit>=1.63,<2", project["optional-dependencies"]["demo"])
        self.assertEqual(
            project["scripts"]["j-gamelqa-demo"],
            "j_gamelqa.demo_cli:main",
        )
        self.assertEqual(project["version"], "1.0.0")

    def test_cli_without_streamlit_returns_clear_install_message(self):
        error = StringIO()
        with (
            patch.object(sys, "argv", ["j-gamelqa-demo"]),
            patch.object(demo_cli, "find_spec", return_value=None),
            patch("sys.stderr", error),
        ):
            exit_code = demo_cli.main()
        self.assertEqual(exit_code, 1)
        self.assertIn('pip install -e ".[demo]"', error.getvalue())
        self.assertNotIn("Traceback", error.getvalue())

    def test_status_check_uses_model_list_without_generation(self):
        response = FakeHTTPResponse(
            b'{"models":[{"name":"qwen3.5:9b"}]}'
        )
        with patch(
            "j_gamelqa.demo_service.urllib.request.urlopen",
            return_value=response,
        ) as urlopen_mock:
            status = check_ollama_status()
        request = urlopen_mock.call_args.args[0]
        self.assertTrue(request.full_url.endswith("/api/tags"))
        self.assertNotIn("generate", request.full_url)
        self.assertEqual(status.service, "available")
        self.assertEqual(status.model, "available")

    def test_examples_are_original_demo_inputs_not_benchmark_ids(self):
        self.assertEqual(len(DEMO_EXAMPLES), 3)
        source_text = " ".join(
            str(value)
            for example in DEMO_EXAMPLES.values()
            for value in example.values()
        )
        self.assertNotIn("TEST_", source_text)
        self.assertNotIn("DEV_", source_text)
        self.assertTrue(any("{item_count}" in item["source_zh"] for item in DEMO_EXAMPLES.values()))

    def test_demo_runtime_source_has_no_benchmark_file_dependency(self):
        for relative_path in (
            "src/j_gamelqa/demo_service.py",
            "src/j_gamelqa/demo_app.py",
            "src/j_gamelqa/demo_cli.py",
        ):
            text = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8").lower()
            self.assertNotIn("data/test", text, relative_path)
            self.assertNotIn("test_annotations", text, relative_path)
            self.assertNotIn("dev_annotations", text, relative_path)


if __name__ == "__main__":
    unittest.main()
