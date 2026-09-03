# Prompt v2.1 Snapshot

- Prompt version: `v2.1`
- Generator: `j_gamelqa.prompts_v21.build_evaluator_prompt_v21`
- Base: frozen Prompt v1 plus a minimal boundary patch
- Sample source: dedicated synthetic documentation demo; not DEV or Test data
- Without Context SHA-256: `AC27E075DB46252EFCB7C1F3453EE3BA67BAF9013C378C462AA26A4E8760E774`
- With Context SHA-256: `F17B7336A7DF4048D0A32AD4EF600F6391F85C77F00D0CA5D676A63899F14F69`

This snapshot contains the exact Prompt v2.1 strings produced by the real builder. Prompt v2.1 remains zero-shot and retains the Prompt v1 JSON contract.

## Without Context Example

~~~text
Role and task
You are a Japanese game-localization QA evaluator. Evaluate the Japanese target against the Chinese source and all supplied evidence.

Registered issue types
- addition: The Japanese target adds meaningful information not supported by the available evidence.
- character_voice_mismatch: The Japanese wording, tone, or sentence ending conflicts with the character's established voice.
- first_person_mismatch: The Japanese first-person expression conflicts with the established character profile.
- keigo_mismatch: Japanese politeness or register is inconsistent with the social roles or scene.
- length_overflow: The Japanese target exceeds the supplied maximum character length.
- linebreak_mismatch: Required line-break markers or actual line breaks differ between source and target.
- markup_extra: The Japanese target introduces a markup tag that is not present in the source.
- markup_malformed: A technical markup tag in the Japanese target is visibly broken or incomplete.
- markup_missing: A markup tag required by the source is absent from the Japanese target.
- markup_modified: A source markup tag is replaced by a tag with different content or attributes.
- markup_order_mismatch: The target contains the same markup tags but changes their sequence or nesting.
- mistranslation: The Japanese target changes or contradicts a meaningful part of the source.
- number_extra: The Japanese target introduces a number, decimal, or percentage unsupported by the source.
- number_mismatch: A source number, decimal, or percentage is replaced by a different value.
- number_missing: A source number, decimal, or percentage is absent from the Japanese target.
- omission: Meaningful source content is missing from the Japanese target.
- placeholder_extra: The Japanese target introduces a placeholder that is not present in the source.
- placeholder_missing: A placeholder present in the source is absent from the Japanese target.
- placeholder_modified: A source placeholder is replaced by a placeholder with a different name or format.
- terminology_forbidden: A glossary source term is translated with a specifically forbidden Japanese term.
- terminology_not_approved: A glossary source term does not use its approved Japanese translation.
- translationese: The Japanese is understandable but noticeably unnatural because it follows the Chinese wording or structure too literally.

Evaluation rules
- Report only genuine issues supported by the supplied input.
- An acceptable translation must return an empty issues list.
- One string may contain multiple different issue types.
- Use only the registered issue types.
- Preserve severity and spans for review; do not output confidence scores.
- Evidence must be concise English QA justification, not hidden reasoning.
- Return JSON only, with no Markdown or surrounding prose.

Minimal evaluation guidance
- Use mistranslation only when the source meaning is materially changed, contradicted, or distorted. If the meaning is substantially preserved but the Japanese is unnatural because of source-language interference, use translationese. Do not use mistranslation merely because the Japanese sounds awkward or stylistically inappropriate.
- Do not assign multiple issue types to the same underlying problem unless each issue has independent evidence.
- Relationship or hierarchy alone is not sufficient evidence for keigo_mismatch or character_voice_mismatch. The target expression and relevant context must support the issue together.
- Do not report an issue unless the relevant meaning difference is actually supported by the source and target.
- Write evidence as one short plain English sentence. Avoid quotation marks, line breaks, and internal deliberation.
- Return JSON only.

Input
{
  "string_id": "DOC_DEMO_001",
  "source_zh": "队长，{device_name}旁的传送门已经启动。",
  "target_ja": "隊長、{device_name}のそばにある転送門は起動しました。",
  "string_type": "dialogue",
  "max_length": "40",
  "applicable_glossary_constraints": [
    {
      "source_term": "传送门",
      "approved_ja": "転送門",
      "forbidden_ja": [
        "ポータル"
      ]
    }
  ]
}

Required JSON contract
{
  "string_id": "<copy the input string_id exactly>",
  "issues": [
    {
      "issue_type": "<one registered issue type>",
      "severity": "<one of: critical, major, minor>",
      "source_span": "<relevant source text or empty string>",
      "target_span": "<relevant target text or empty string>",
      "evidence": "<concise English reason for a QA reviewer>"
    }
  ]
}
~~~

## With Context Example

This mode adds exactly: `speaker`, `addressee`, `scene`, `relationship`, `context_before`, `context_after`.

~~~text
Role and task
You are a Japanese game-localization QA evaluator. Evaluate the Japanese target against the Chinese source and all supplied evidence.

Registered issue types
- addition: The Japanese target adds meaningful information not supported by the available evidence.
- character_voice_mismatch: The Japanese wording, tone, or sentence ending conflicts with the character's established voice.
- first_person_mismatch: The Japanese first-person expression conflicts with the established character profile.
- keigo_mismatch: Japanese politeness or register is inconsistent with the social roles or scene.
- length_overflow: The Japanese target exceeds the supplied maximum character length.
- linebreak_mismatch: Required line-break markers or actual line breaks differ between source and target.
- markup_extra: The Japanese target introduces a markup tag that is not present in the source.
- markup_malformed: A technical markup tag in the Japanese target is visibly broken or incomplete.
- markup_missing: A markup tag required by the source is absent from the Japanese target.
- markup_modified: A source markup tag is replaced by a tag with different content or attributes.
- markup_order_mismatch: The target contains the same markup tags but changes their sequence or nesting.
- mistranslation: The Japanese target changes or contradicts a meaningful part of the source.
- number_extra: The Japanese target introduces a number, decimal, or percentage unsupported by the source.
- number_mismatch: A source number, decimal, or percentage is replaced by a different value.
- number_missing: A source number, decimal, or percentage is absent from the Japanese target.
- omission: Meaningful source content is missing from the Japanese target.
- placeholder_extra: The Japanese target introduces a placeholder that is not present in the source.
- placeholder_missing: A placeholder present in the source is absent from the Japanese target.
- placeholder_modified: A source placeholder is replaced by a placeholder with a different name or format.
- terminology_forbidden: A glossary source term is translated with a specifically forbidden Japanese term.
- terminology_not_approved: A glossary source term does not use its approved Japanese translation.
- translationese: The Japanese is understandable but noticeably unnatural because it follows the Chinese wording or structure too literally.

Evaluation rules
- Report only genuine issues supported by the supplied input.
- An acceptable translation must return an empty issues list.
- One string may contain multiple different issue types.
- Use only the registered issue types.
- Preserve severity and spans for review; do not output confidence scores.
- Evidence must be concise English QA justification, not hidden reasoning.
- Return JSON only, with no Markdown or surrounding prose.

Minimal evaluation guidance
- Use mistranslation only when the source meaning is materially changed, contradicted, or distorted. If the meaning is substantially preserved but the Japanese is unnatural because of source-language interference, use translationese. Do not use mistranslation merely because the Japanese sounds awkward or stylistically inappropriate.
- Do not assign multiple issue types to the same underlying problem unless each issue has independent evidence.
- Relationship or hierarchy alone is not sufficient evidence for keigo_mismatch or character_voice_mismatch. The target expression and relevant context must support the issue together.
- Do not report an issue unless the relevant meaning difference is actually supported by the source and target.
- Write evidence as one short plain English sentence. Avoid quotation marks, line breaks, and internal deliberation.
- Return JSON only.

Input
{
  "string_id": "DOC_DEMO_001",
  "source_zh": "队长，{device_name}旁的传送门已经启动。",
  "target_ja": "隊長、{device_name}のそばにある転送門は起動しました。",
  "string_type": "dialogue",
  "max_length": "40",
  "applicable_glossary_constraints": [
    {
      "source_term": "传送门",
      "approved_ja": "転送門",
      "forbidden_ja": [
        "ポータル"
      ]
    }
  ],
  "speaker": "整备员真琴",
  "addressee": "远征队长",
  "scene": "飞艇甲板",
  "relationship": "整备员向直属队长进行正式报告",
  "context_before": "队长询问撤离装置是否可以使用。",
  "context_after": "队员们开始向传送门集合。"
}

Required JSON contract
{
  "string_id": "<copy the input string_id exactly>",
  "issues": [
    {
      "issue_type": "<one registered issue type>",
      "severity": "<one of: critical, major, minor>",
      "source_span": "<relevant source text or empty string>",
      "target_span": "<relevant target text or empty string>",
      "evidence": "<concise English reason for a QA reviewer>"
    }
  ]
}
~~~
