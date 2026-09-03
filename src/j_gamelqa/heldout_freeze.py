"""Hash-only preflight for the first and final held-out evaluation."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from j_gamelqa.io import load_glossary
from j_gamelqa.prompt_snapshot import build_snapshot_prompts
from j_gamelqa.prompt_v21_snapshot import build_v21_snapshot_prompts


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_SHA256 = "39E01B0C1507A55D34CDAFB1F4E0421B5654FDCBC96BBD6045D192CF11BC06A2"
EXPECTED_HASHES = {
    "test.csv": "2EB9565F7334DEB6EC552578ECDB7F7A697DA097F08DBED14F12BAFCCED2E785",
    "test_annotations.csv": "0C92B3E65779E3DAE06B0E1D9569CFCFC494BEA10A4DE1CBB22837F303E9821B",
    "v1_without_context": "F36162A11642FF070F1EBCBE4A04AA1B82864FEFCC61AE23117BF0F6A495218A",
    "v1_with_context": "11635FC05B3ED316F65978C4575C049787498E453094369937D8FF2E7B5CD906",
    "v21_without_context": "AC27E075DB46252EFCB7C1F3453EE3BA67BAF9013C378C462AA26A4E8760E774",
    "v21_with_context": "F17B7336A7DF4048D0A32AD4EF600F6391F85C77F00D0CA5D676A63899F14F69",
}

RULE_SOURCE_FILES = (
    "src/j_gamelqa/rule_engine.py",
    "src/j_gamelqa/rules/placeholder.py",
    "src/j_gamelqa/rules/number.py",
    "src/j_gamelqa/rules/markup.py",
    "src/j_gamelqa/rules/linebreak.py",
    "src/j_gamelqa/rules/length.py",
    "src/j_gamelqa/rules/terminology.py",
)

HELDOUT_RESULT_FILES = (
    "test_rule_predictions.json",
    "test_rule_evaluation.json",
    "test_rule_bad_cases.json",
    "test_qwen35_prompt_v1_config.json",
    "test_qwen35_prompt_v1_raw.jsonl",
    "test_qwen35_prompt_v1_predictions.json",
    "test_qwen35_prompt_v1_evaluation.json",
    "test_qwen35_prompt_v1_bad_cases.json",
    "test_qwen35_prompt_v21_config.json",
    "test_qwen35_prompt_v21_raw.jsonl",
    "test_qwen35_prompt_v21_predictions.json",
    "test_qwen35_prompt_v21_evaluation.json",
    "test_qwen35_prompt_v21_bad_cases.json",
    "test_hybrid_prompt_v1_predictions.json",
    "test_hybrid_prompt_v1_evaluation.json",
    "test_hybrid_prompt_v1_bad_cases.json",
    "test_hybrid_prompt_v21_predictions.json",
    "test_hybrid_prompt_v21_evaluation.json",
    "test_hybrid_prompt_v21_bad_cases.json",
    "heldout_prediction_freeze.json",
    "heldout_method_comparison_v1.json",
    "heldout_method_comparison_v1.csv",
    "heldout_evaluation_freeze_manifest.json",
)


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def build_preflight_payload(project_root: str | Path = PROJECT_ROOT) -> dict:
    root = Path(project_root)
    glossary = load_glossary(root / "data" / "glossary.csv")
    v1 = build_snapshot_prompts(glossary)
    v21 = build_v21_snapshot_prompts(glossary)
    actual = {
        "test.csv": sha256_file(root / "data" / "test.csv"),
        "test_annotations.csv": sha256_file(
            root / "data" / "test_annotations.csv"
        ),
        "v1_without_context": sha256_text(v1["without_context"]),
        "v1_with_context": sha256_text(v1["with_context"]),
        "v21_without_context": sha256_text(v21["without_context"]),
        "v21_with_context": sha256_text(v21["with_context"]),
    }
    mismatches = {
        name: {"expected": EXPECTED_HASHES[name], "actual": value}
        for name, value in actual.items()
        if value != EXPECTED_HASHES[name]
    }
    protocol_path = root / "docs" / "heldout_evaluation_protocol.md"
    protocol_hash = sha256_file(protocol_path)
    if protocol_hash != PROTOCOL_SHA256:
        mismatches["heldout_evaluation_protocol.md"] = {
            "expected": PROTOCOL_SHA256,
            "actual": protocol_hash,
        }
    existing_outputs = [
        name for name in HELDOUT_RESULT_FILES if (root / "outputs" / name).exists()
    ]
    if mismatches or existing_outputs:
        raise RuntimeError(
            f"Held-out preflight failed: mismatches={mismatches}, "
            f"existing_outputs={existing_outputs}"
        )
    source_files = [
        *RULE_SOURCE_FILES,
        "src/j_gamelqa/prompts.py",
        "src/j_gamelqa/prompts_v21.py",
        "src/j_gamelqa/taxonomy.py",
        "src/j_gamelqa/hybrid.py",
        "src/j_gamelqa/evaluate.py",
    ]
    return {
        "freeze_id": "heldout_evaluation_preflight_v1",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "status": "ready_for_first_and_final_heldout_inference",
        "annotation_content_loaded": False,
        "hashes": actual,
        "protocol_sha256": protocol_hash,
        "source_sha256": {
            path: sha256_file(root / path) for path in source_files
        },
        "planned_methods": [
            "rule_only",
            "llm_prompt_v1_with_context",
            "llm_prompt_v2.1_with_context",
            "hybrid_prompt_v1",
            "hybrid_prompt_v2.1",
        ],
    }


def write_preflight_manifest(output_path: str | Path) -> Path:
    destination = Path(output_path)
    if destination.exists():
        raise FileExistsError(f"preflight manifest already exists: {destination}")
    payload = build_preflight_payload()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze held-out evaluation preflight.")
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "heldout_pre_evaluation_freeze.json",
    )
    args = parser.parse_args()
    print(write_preflight_manifest(args.output))


if __name__ == "__main__":
    main()
