"""Single source of truth for the current J-GameLQA issue taxonomy."""


RULE_ADDRESSABLE_ISSUE_TYPES = frozenset(
    {
        "placeholder_missing",
        "placeholder_modified",
        "placeholder_extra",
        "number_mismatch",
        "number_missing",
        "number_extra",
        "markup_malformed",
        "markup_modified",
        "markup_missing",
        "markup_extra",
        "markup_order_mismatch",
        "linebreak_mismatch",
        "length_overflow",
        "terminology_forbidden",
        "terminology_not_approved",
    }
)

LLM_REQUIRED_ISSUE_TYPES = frozenset(
    {
        "omission",
        "addition",
        "mistranslation",
        "translationese",
        "keigo_mismatch",
        "first_person_mismatch",
        "character_voice_mismatch",
    }
)

REGISTERED_ISSUE_TYPES = RULE_ADDRESSABLE_ISSUE_TYPES | LLM_REQUIRED_ISSUE_TYPES


ISSUE_TYPE_DEFINITIONS = {
    "placeholder_missing": (
        "A placeholder present in the source is absent from the Japanese target."
    ),
    "placeholder_modified": (
        "A source placeholder is replaced by a placeholder with a different name "
        "or format."
    ),
    "placeholder_extra": (
        "The Japanese target introduces a placeholder that is not present in the source."
    ),
    "number_mismatch": (
        "A source number, decimal, or percentage is replaced by a different value."
    ),
    "number_missing": (
        "A source number, decimal, or percentage is absent from the Japanese target."
    ),
    "number_extra": (
        "The Japanese target introduces a number, decimal, or percentage unsupported "
        "by the source."
    ),
    "markup_malformed": (
        "A technical markup tag in the Japanese target is visibly broken or incomplete."
    ),
    "markup_modified": (
        "A source markup tag is replaced by a tag with different content or attributes."
    ),
    "markup_missing": (
        "A markup tag required by the source is absent from the Japanese target."
    ),
    "markup_extra": (
        "The Japanese target introduces a markup tag that is not present in the source."
    ),
    "markup_order_mismatch": (
        "The target contains the same markup tags but changes their sequence or nesting."
    ),
    "linebreak_mismatch": (
        "Required line-break markers or actual line breaks differ between source and target."
    ),
    "length_overflow": (
        "The Japanese target exceeds the supplied maximum character length."
    ),
    "terminology_forbidden": (
        "A glossary source term is translated with a specifically forbidden Japanese term."
    ),
    "terminology_not_approved": (
        "A glossary source term does not use its approved Japanese translation."
    ),
    "omission": (
        "Meaningful source content is missing from the Japanese target."
    ),
    "addition": (
        "The Japanese target adds meaningful information not supported by the available "
        "evidence."
    ),
    "mistranslation": (
        "The Japanese target changes or contradicts a meaningful part of the source."
    ),
    "translationese": (
        "The Japanese is understandable but noticeably unnatural because it follows "
        "the Chinese wording or structure too literally."
    ),
    "keigo_mismatch": (
        "Japanese politeness or register is inconsistent with the social roles or scene."
    ),
    "first_person_mismatch": (
        "The Japanese first-person expression conflicts with the established character profile."
    ),
    "character_voice_mismatch": (
        "The Japanese wording, tone, or sentence ending conflicts with the character's "
        "established voice."
    ),
}


if set(ISSUE_TYPE_DEFINITIONS) != REGISTERED_ISSUE_TYPES:
    raise RuntimeError("Every registered issue type must have exactly one definition.")
