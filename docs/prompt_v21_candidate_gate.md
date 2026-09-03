# Prompt v2.1 Candidate Selection Rule

This rule is registered before the one formal Prompt v2.1 Development inference run. It must not be changed after inspecting that run.

Prompt v2.1 advances to held-out evaluation only if every condition passes:

1. LLM-required Precision is strictly greater than `0.6053`.
2. LLM-required Recall is at least `0.8800`.
3. LLM-required F1 is at least `0.7302`.
4. Hybrid F1 is at least `0.8376`.
5. All 48 responses pass the existing strict protocol and provider failures equal zero.

If any condition fails, Prompt v1 remains the champion. Prompt v2.1 is still preserved as the final Development prompt experiment, no Prompt v2.2/v3 DEV iteration follows, and candidate selection proceeds without further Development hill-climbing.

The executable source of truth is `j_gamelqa.candidate_selection.evaluate_candidate_gate`.
