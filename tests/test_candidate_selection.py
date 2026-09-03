import unittest

from j_gamelqa.candidate_selection import evaluate_candidate_gate


def metrics(precision, recall, f1):
    return {"precision": precision, "recall": recall, "f1": f1}


def protocol(successes=48, failures=0):
    return {
        "protocol_successful_responses": successes,
        "provider_failures": failures,
    }


class CandidateSelectionTests(unittest.TestCase):
    def test_candidate_passes_only_when_every_pre_registered_gate_passes(self):
        result = evaluate_candidate_gate(
            metrics(0.61, 0.88, 0.74),
            metrics(0.75, 0.95, 0.84),
            protocol(),
        )
        self.assertTrue(result["promoted_to_held_out_candidate"])

    def test_precision_gate_is_strictly_greater(self):
        result = evaluate_candidate_gate(
            metrics(0.6053, 0.90, 0.74),
            metrics(0.75, 0.95, 0.84),
            protocol(),
        )
        self.assertFalse(result["checks"]["llm_required_precision"])
        self.assertEqual(result["decision"], "prompt_v1_remains_champion")

    def test_protocol_requires_all_48_successful_responses(self):
        result = evaluate_candidate_gate(
            metrics(0.61, 0.90, 0.74),
            metrics(0.75, 0.95, 0.84),
            protocol(successes=47),
        )
        self.assertFalse(result["checks"]["protocol_success"])
        self.assertFalse(result["promoted_to_held_out_candidate"])


if __name__ == "__main__":
    unittest.main()
