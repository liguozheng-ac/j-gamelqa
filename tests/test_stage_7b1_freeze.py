import hashlib
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

V2_FROZEN_SHA256 = {
    "src/j_gamelqa/prompts_v2.py": "59E97E8418A0D2C6F2BA0AEB2B99E23EA66382581361FCBAA0D56C88023F590B",
    "docs/prompt_v2_snapshot.md": "7C59C95E7D7CF901BB4E58B9292C433C3155B786AF87CD9D903F3F4FEA28EA15",
    "outputs/qwen35_9b_with_context_prompt_v2_dev_config.json": "CF7F23018B497709574F4F6C9C2018C814E4EFE2713BE272AFF106148495681A",
    "outputs/qwen35_9b_with_context_prompt_v2_dev_raw.jsonl": "C7BACF29208325E759EDAB17FC1FC223B97D6D81BA4F6BE3A9F799235F988334",
    "outputs/qwen35_9b_with_context_prompt_v2_dev_predictions.json": "8568168443AC4784A242EC9A300765775143151180B1C34D0526FE6F9EBE69BB",
    "outputs/qwen35_9b_with_context_prompt_v2_dev_evaluation.json": "0E885F5489209F4B4E0F5340E07D296CAE4591D8BC0A8B30E88BADC8E460CC08",
    "outputs/qwen35_9b_with_context_prompt_v2_dev_bad_cases.json": "910D47BCF954BB889DCC6E6668A071521CD7DD01A2DC109604D5B0FC32D948FE",
    "outputs/prompt_v1_vs_v2_dev_comparison.json": "ED6D8EDEC40D81D157897A9141F5F56F791A5B427EE53D9C9922FC88D685AB31",
    "outputs/hybrid_rule_qwen35_context_prompt_v2_dev_config.json": "DB4B72C41A572BE786194704A67BE9332E2E3C80C75ACED43A20EB18B291A21F",
    "outputs/hybrid_rule_qwen35_context_prompt_v2_dev_predictions.json": "59057AD882638BEA2E3790C6E2F1075D650FD8542BFCD201DFBD179809289535",
    "outputs/hybrid_rule_qwen35_context_prompt_v2_dev_evaluation.json": "038CE349747A16C1C62BAA8F05C8A1305D707CA120EA87DB760C2C8E968D1D32",
    "outputs/hybrid_rule_qwen35_context_prompt_v2_dev_bad_cases.json": "0CFEDEB9595920DAC88E2D64E994091D02F6F21A6056D539C39A8E4A5D4F6DA0",
    "outputs/hybrid_v1_vs_prompt_v2_dev_comparison.json": "5F271EBF5422652017A111D6CADEA2BE26F0550F11F8CC22513C782AFCF1827B",
}

CANDIDATE_GATE_SHA256 = {
    "src/j_gamelqa/candidate_selection.py": "931DDF2D372B1CB1C3B6A3B41E6DFE74BB8CDA76BE29A23377667D6D2518D408",
    "docs/prompt_v21_candidate_gate.md": "3BF4C6159C591B4A91DA6635C25298004E93541F59D8DF19D39B2FCAF0B07F87",
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


class Stage7B1FreezeTests(unittest.TestCase):
    def test_prompt_v2_code_snapshot_and_artifacts_remain_frozen(self):
        for relative_path, expected in V2_FROZEN_SHA256.items():
            self.assertEqual(
                sha256(PROJECT_ROOT / relative_path), expected, relative_path
            )

    def test_candidate_gate_is_the_pre_inference_registered_version(self):
        for relative_path, expected in CANDIDATE_GATE_SHA256.items():
            self.assertEqual(
                sha256(PROJECT_ROOT / relative_path), expected, relative_path
            )


if __name__ == "__main__":
    unittest.main()
