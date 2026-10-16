"""Build a small, deterministic manifest for the frozen J-GameLQA v1 release."""

import argparse
import csv
import hashlib
import json
from pathlib import Path

from j_gamelqa.io import load_glossary
from j_gamelqa.prompt_v21_snapshot import build_v21_snapshot_prompts
from j_gamelqa.heldout_freeze import sha256_text


PROJECT_ROOT = Path(__file__).resolve().parents[2]
VERSION = "1.0.0"
FINAL_CANDIDATE = {
    "rule": "Rule Baseline v1",
    "llm": "Qwen3.5-9B",
    "prompt": "Prompt v2.1",
    "input_mode": "with_context",
    "hybrid_policy": {
        "rule_addressable": "rule",
        "llm_required": "context_aware_llm",
    },
}
EXPECTED_PROMPT_SHA256 = (
    "F17B7336A7DF4048D0A32AD4EF600F6391F85C77F00D0CA5D676A63899F14F69"
)
EXPECTED_TEST_SHA256 = (
    "2EB9565F7334DEB6EC552578ECDB7F7A697DA097F08DBED14F12BAFCCED2E785"
)
EXPECTED_HELDOUT_COMPARISON_SHA256 = (
    "31208B6B2BF2B3AC1CFDFD3DA14ABC8A76F85EED43A4D1B5AB5FC602F5A8D329"
)
EXPECTED_HELDOUT_RESULT = {
    "tp": 58,
    "fp": 41,
    "fn": 8,
    "precision": 0.5858585858585859,
    "recall": 0.8787878787878788,
    "f1": 0.7030303030303031,
}
RELEASE_DOCUMENTS = (
    "README.md",
    "README.zh-CN.md",
    "RELEASE_NOTES.md",
    "docs/architecture.md",
    "docs/experiment_flow.md",
    "docs/interview_deep_dive.md",
    "docs/job_talk_tracks.md",
    "docs/portfolio_onepager.md",
    "docs/resume_cn.md",
    "docs/reproducibility.md",
    "docs/local_demo.md",
    "docs/public_release_audit.md",
    "docs/github_release_checklist.md",
    "docs/git_commit_plan.md",
    "docs/heldout_evaluation_results.md",
    "docs/assets/j-gamelqa-architecture.svg",
    "docs/assets/j-gamelqa-experiment-flow.svg",
)


def sha256_file(path: str | Path) -> str:
    """Return an uppercase SHA-256 for one file."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


def _csv_row_count(path: Path) -> int:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def build_release_manifest(
    project_root: str | Path = PROJECT_ROOT,
    automated_test_count: int = 0,
    demo_smoke_inference_calls: int = 0,
) -> dict[str, object]:
    """Verify frozen inputs and return the deterministic v1 release manifest."""
    root = Path(project_root)
    glossary = load_glossary(root / "data" / "glossary.csv")
    prompt = build_v21_snapshot_prompts(glossary)["with_context"]
    prompt_hash = sha256_text(prompt)
    test_hash = sha256_file(root / "data" / "test.csv")
    comparison_path = root / "outputs" / "heldout_method_comparison_v1.json"
    comparison_hash = sha256_file(comparison_path)

    expected_hashes = {
        "prompt_v21_with_context": EXPECTED_PROMPT_SHA256,
        "test.csv": EXPECTED_TEST_SHA256,
        "heldout_method_comparison_v1.json": EXPECTED_HELDOUT_COMPARISON_SHA256,
    }
    actual_hashes = {
        "prompt_v21_with_context": prompt_hash,
        "test.csv": test_hash,
        "heldout_method_comparison_v1.json": comparison_hash,
    }
    mismatches = {
        name: {"expected": expected_hashes[name], "actual": value}
        for name, value in actual_hashes.items()
        if value != expected_hashes[name]
    }
    if mismatches:
        raise RuntimeError(f"frozen release input mismatch: {mismatches}")

    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    result = comparison["methods"]["Hybrid Prompt v2.1"]["overall"]
    if result != EXPECTED_HELDOUT_RESULT:
        raise RuntimeError(
            "frozen Hybrid Prompt v2.1 metrics do not match the v1 release result"
        )

    return {
        "release": "J-GameLQA v1",
        "version": VERSION,
        "release_date": "2026-09-04",
        "status": "frozen_portfolio_release",
        "final_candidate": FINAL_CANDIDATE,
        "heldout_result": result,
        "prompt_sha256": prompt_hash,
        "test_sha256": test_hash,
        "heldout_result_artifact": str(
            comparison_path.relative_to(root)
        ).replace("\\", "/"),
        "heldout_result_artifact_sha256": comparison_hash,
        "heldout_freeze_manifest_sha256": sha256_file(
            root / "outputs" / "heldout_evaluation_freeze_manifest.json"
        ),
        "license": {
            "type": "MIT",
            "file": "LICENSE",
            "sha256": sha256_file(root / "LICENSE"),
        },
        "pyproject_sha256": sha256_file(root / "pyproject.toml"),
        "demo": {
            "available": True,
            "framework": "Streamlit",
            "entry_point": "j-gamelqa-demo",
            "optional_dependency": "streamlit>=1.63,<2",
            "smoke_inference_calls": demo_smoke_inference_calls,
        },
        "document_sha256": {
            path: sha256_file(root / path) for path in RELEASE_DOCUMENTS
        },
        "counts": {
            "automated_unittest_count": automated_test_count,
            "development_sample_count": _csv_row_count(root / "data" / "dev.csv"),
            "held_out_test_sample_count": _csv_row_count(root / "data" / "test.csv"),
            "held_out_reference_detection_count": _csv_row_count(
                root / "data" / "test_annotations.csv"
            ),
        },
        "policy": {
            "ollama_calls_during_release_packaging": demo_smoke_inference_calls,
            "held_out_test_inference_during_release_packaging": 0,
            "held_out_test_evaluation_during_release_packaging": 0,
            "no_retuning": (
                "Future development requires Test v2 or an external "
                "human-reviewed evaluation set."
            ),
        },
    }


def write_release_manifest(
    output_path: str | Path,
    automated_test_count: int,
    demo_smoke_inference_calls: int = 0,
) -> Path:
    """Write one new release manifest without overwriting an existing file."""
    destination = Path(output_path)
    if destination.exists():
        raise FileExistsError(f"release manifest already exists: {destination}")
    payload = build_release_manifest(
        automated_test_count=automated_test_count,
        demo_smoke_inference_calls=demo_smoke_inference_calls,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the frozen J-GameLQA v1 release manifest."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "v1_release_manifest.json",
    )
    parser.add_argument("--automated-test-count", type=int, required=True)
    parser.add_argument("--demo-smoke-inference-calls", type=int, default=0)
    args = parser.parse_args()
    print(
        write_release_manifest(
            args.output,
            args.automated_test_count,
            args.demo_smoke_inference_calls,
        )
    )


if __name__ == "__main__":
    main()
