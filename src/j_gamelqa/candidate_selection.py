"""Pre-registered candidate gate for the final Development prompt experiment."""


GATE_VERSION = "stage_7b1_pre_registered_v1"

THRESHOLDS = {
    "llm_required_precision_strictly_greater_than": 0.6053,
    "llm_required_recall_at_least": 0.8800,
    "llm_required_f1_at_least": 0.7302,
    "hybrid_f1_at_least": 0.8376,
    "protocol_successful_responses_required": 48,
    "provider_failures_allowed": 0,
}


def evaluate_candidate_gate(
    llm_required: dict[str, float | int],
    hybrid_overall: dict[str, float | int],
    protocol: dict[str, object],
) -> dict[str, object]:
    """Apply the gate exactly as registered before Prompt v2.1 inference."""
    checks = {
        "llm_required_precision": (
            float(llm_required["precision"])
            > THRESHOLDS["llm_required_precision_strictly_greater_than"]
        ),
        "llm_required_recall": (
            float(llm_required["recall"])
            >= THRESHOLDS["llm_required_recall_at_least"]
        ),
        "llm_required_f1": (
            float(llm_required["f1"])
            >= THRESHOLDS["llm_required_f1_at_least"]
        ),
        "hybrid_f1": (
            float(hybrid_overall["f1"])
            >= THRESHOLDS["hybrid_f1_at_least"]
        ),
        "protocol_success": (
            int(protocol["protocol_successful_responses"])
            == THRESHOLDS["protocol_successful_responses_required"]
            and int(protocol["provider_failures"])
            == THRESHOLDS["provider_failures_allowed"]
        ),
    }
    promoted = all(checks.values())
    return {
        "gate_version": GATE_VERSION,
        "registered_before_formal_inference": True,
        "thresholds": THRESHOLDS,
        "checks": checks,
        "promoted_to_held_out_candidate": promoted,
        "decision": (
            "prompt_v1_and_prompt_v2.1_are_held_out_candidates"
            if promoted
            else "prompt_v1_remains_champion"
        ),
    }
