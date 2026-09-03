# Prompt v1 Snapshot

- Prompt version: `v1`
- Generator: `j_gamelqa.prompts.build_evaluator_prompt`
- Sample source: dedicated synthetic documentation demo; not DEV or Test data
- Without Context SHA-256: `F36162A11642FF070F1EBCBE4A04AA1B82864FEFCC61AE23117BF0F6A495218A`
- With Context SHA-256: `11635FC05B3ED316F65978C4575C049787498E453094369937D8FF2E7B5CD906`

This file is generated from the real shared Prompt Builder. It is a readable snapshot of the exact strings supplied to the provider, not a manually rewritten approximation.

## Shared Prompt v1

Both modes use the same Role and task, 22-type issue taxonomy, evaluation rules, and required JSON output contract. The only intended difference is the input payload.

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
