import unittest

from j_gamelqa.taxonomy import (
    ISSUE_TYPE_DEFINITIONS,
    LLM_REQUIRED_ISSUE_TYPES,
    REGISTERED_ISSUE_TYPES,
    RULE_ADDRESSABLE_ISSUE_TYPES,
)


class TaxonomyTests(unittest.TestCase):
    def test_taxonomy_groups_are_disjoint_and_complete(self):
        self.assertTrue(RULE_ADDRESSABLE_ISSUE_TYPES.isdisjoint(LLM_REQUIRED_ISSUE_TYPES))
        self.assertEqual(
            REGISTERED_ISSUE_TYPES,
            RULE_ADDRESSABLE_ISSUE_TYPES | LLM_REQUIRED_ISSUE_TYPES,
        )

    def test_current_checker_issue_types_are_registered(self):
        current_rule_types = {
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
        self.assertEqual(current_rule_types, RULE_ADDRESSABLE_ISSUE_TYPES)

    def test_every_registered_type_has_one_non_empty_definition(self):
        self.assertEqual(set(ISSUE_TYPE_DEFINITIONS), REGISTERED_ISSUE_TYPES)
        self.assertTrue(
            all(definition.strip() for definition in ISSUE_TYPE_DEFINITIONS.values())
        )
