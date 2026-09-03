import json
import unittest

import pandas as pd

from j_gamelqa.evaluate import evaluate_detections
from j_gamelqa.llm_evaluator import parse_llm_response
from j_gamelqa.models import Issue


REFERENCE_COLUMNS = (
    "annotation_id",
    "string_id",
    "issue_type",
    "severity",
    "source_span",
    "target_span",
    "evidence",
    "annotation_note",
)


def issue_payload(
    issue_type="keigo_mismatch",
    severity="major",
    source_span="请您过目",
    target_span="見てくれ",
    evidence="A subordinate uses an overly casual request to a superior.",
):
    return {
        "issue_type": issue_type,
        "severity": severity,
        "source_span": source_span,
        "target_span": target_span,
        "evidence": evidence,
    }


def response(string_id="DEV_008", issues=None):
    return json.dumps(
        {"string_id": string_id, "issues": [] if issues is None else issues},
        ensure_ascii=False,
    )


def references(*rows):
    return pd.DataFrame(rows, columns=REFERENCE_COLUMNS)


def reference(
    annotation_id="ANN_TEST",
    string_id="DEV_008",
    issue_type="keigo_mismatch",
    severity="major",
    source_span="reference span",
    target_span="reference target span",
):
    return (
        annotation_id,
        string_id,
        issue_type,
        severity,
        source_span,
        target_span,
        "{}",
        "test reference",
    )


class LLMResponseParserTests(unittest.TestCase):
    def test_valid_clean_json_produces_zero_issues(self):
        result = parse_llm_response(response(), "DEV_008")
        self.assertTrue(result.is_valid)
        self.assertEqual(result.predictions, [])
    def test_valid_single_issue_converts_to_shared_issue(self):
        raw_response = response(issues=[issue_payload()])
        result = parse_llm_response(raw_response, "DEV_008")
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.predictions), 1)
        prediction = result.predictions[0]
        self.assertIsInstance(prediction, Issue)
        self.assertEqual(prediction.checker, "japanese_llm")
        self.assertEqual(prediction.issue_type, "keigo_mismatch")
        self.assertEqual(
            prediction.evidence,
            {"reason": "A subordinate uses an overly casual request to a superior."},
        )
        self.assertTrue(prediction.needs_human_review)

    def test_valid_multi_issue_response_preserves_both(self):
        result = parse_llm_response(
            response(
                issues=[
                    issue_payload("number_mismatch"),
                    issue_payload("keigo_mismatch"),
                ]
            ),
            "DEV_008",
        )
        self.assertEqual(
            [prediction.issue_type for prediction in result.predictions],
            ["number_mismatch", "keigo_mismatch"],
        )

    def test_malformed_json_is_parse_failure_and_keeps_raw_response(self):
        raw_response = '{"string_id": "DEV_008", "issues": [}'
        result = parse_llm_response(raw_response, "DEV_008")
        self.assertFalse(result.is_valid)
        self.assertTrue(result.diagnostics.parse_failures)
        self.assertEqual(result.raw_response, raw_response)
        self.assertEqual(result.predictions, [])

    def test_missing_required_field_is_schema_failure(self):
        payload = issue_payload()
        del payload["evidence"]
        result = parse_llm_response(
            response(issues=[payload]), "DEV_008"
        )
        self.assertTrue(result.diagnostics.schema_failures)
        self.assertEqual(result.predictions, [])

    def test_wrong_field_types_are_schema_failure(self):
        payload = issue_payload()
        payload["issue_type"] = 123
        payload["severity"] = ["major"]
        result = parse_llm_response(
            response(issues=[payload]), "DEV_008"
        )
        self.assertGreaterEqual(len(result.diagnostics.schema_failures), 2)
        self.assertEqual(result.diagnostics.unknown_issue_types, [])

    def test_wrong_string_id_is_validation_failure(self):
        result = parse_llm_response(
            response("DEV_041", [issue_payload()]), "DEV_040"
        )
        self.assertTrue(result.diagnostics.validation_failures)
        self.assertEqual(result.predictions, [])
        self.assertEqual(result.response_string_id, "DEV_041")

    def test_unknown_issue_type_is_retained_and_reported(self):
        result = parse_llm_response(
            response(issues=[issue_payload("bad_japanese")]), "DEV_008"
        )
        self.assertTrue(result.is_valid)
        self.assertEqual(result.predictions[0].issue_type, "bad_japanese")
        self.assertEqual(
            result.diagnostics.unknown_issue_types, ["bad_japanese"]
        )

    def test_unknown_issue_type_enters_detection_evaluation(self):
        parsed = parse_llm_response(
            response(issues=[issue_payload("bad_japanese")]), "DEV_008"
        )
        evaluation = evaluate_detections(references(), parsed.predictions)
        self.assertEqual(evaluation["overall_micro"]["fp"], 1)
        self.assertEqual(
            evaluation["unknown_prediction_types"], ["bad_japanese"]
        )

    def test_invalid_severity_is_schema_failure(self):
        result = parse_llm_response(
            response(issues=[issue_payload(severity="blocker")]), "DEV_008"
        )
        self.assertTrue(result.diagnostics.schema_failures)
        self.assertEqual(result.predictions, [])

    def test_duplicate_predictions_are_preserved_and_diagnosed(self):
        duplicate = issue_payload()
        result = parse_llm_response(
            response(issues=[duplicate, duplicate.copy()]), "DEV_008"
        )
        self.assertEqual(len(result.predictions), 2)
        self.assertEqual(
            result.diagnostics.duplicate_predictions,
            [
                {
                    "string_id": "DEV_008",
                    "issue_type": "keigo_mismatch",
                    "count": 2,
                }
            ],
        )
        evaluation = evaluate_detections(
            references(reference()), result.predictions
        )
        self.assertEqual(evaluation["overall_micro"]["tp"], 1)
        self.assertEqual(len(evaluation["duplicate_predictions"]), 1)

    def test_span_difference_does_not_change_detection(self):
        parsed = parse_llm_response(
            response(
                issues=[
                    issue_payload(
                        source_span="different source",
                        target_span="different target",
                    )
                ]
            ),
            "DEV_008",
        )
        evaluation = evaluate_detections(
            references(reference()), parsed.predictions
        )
        self.assertEqual(evaluation["overall_micro"]["tp"], 1)

    def test_severity_difference_does_not_change_detection(self):
        parsed = parse_llm_response(
            response(issues=[issue_payload(severity="minor")]), "DEV_008"
        )
        evaluation = evaluate_detections(
            references(reference(severity="major")), parsed.predictions
        )
        self.assertEqual(evaluation["overall_micro"]["tp"], 1)

    def test_unexpected_fields_are_schema_failure(self):
        raw_response = json.dumps(
            {"string_id": "DEV_008", "issues": [], "confidence": 0.92}
        )
        result = parse_llm_response(raw_response, "DEV_008")
        self.assertTrue(result.diagnostics.schema_failures)
        self.assertEqual(result.predictions, [])
