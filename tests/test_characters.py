"""Verify grounded incremental character indexing and spoiler-safe aliases.
Exercises character facts against exact chapter offsets with synthetic French text.
"""

import json
import unittest

from support import LibraryFixture
from reading_companion import characters
from reading_companion.storage import CompanionError


class CharacterTests(LibraryFixture, unittest.TestCase):
    def setUp(self):
        self.setup_library()
        self.book.set_progress(5, finished=True)
        characters.record(self.book, "Élise", 1, "Élise ferme la porte.")
        characters.record(self.book, "Paul", 1, "Paul attend dans le jardin.")

    def test_character_names_resolve_without_duplicate(self):
        characters.record(self.book, "ÉLISE", 1, "Élise ferme la porte.")
        self.assertEqual(len(characters.show(self.book)["characters"]), 2)
        result = characters.show(self.book, "e\u0301lise")
        self.assertEqual(result["character"]["name"], "Élise")

    def test_alias_becomes_visible_only_when_read(self):
        characters.record(self.book, "Élise", 3, "On appelle Élise Lise.", alias="Lise")
        self.assertEqual(characters.show(self.book, "Lise")["character"]["name"], "Élise")
        self.book.set_progress(2, finished=True)
        self.assertIsNone(characters.show(self.book, "Lise")["character"])
        encoded = json.dumps(characters.show(self.book, "Élise"), ensure_ascii=False)
        self.assertNotIn("Lise", encoded)

    def test_exact_position_gates_fact_and_alias(self):
        characters.record(self.book, "Élise", 3, "On appelle Élise Lise.", alias="Lise")
        end = self.book.text(3).index("On appelle Élise Lise.") + len("On appelle Élise Lise.")
        self.book.set_progress(3, offset=end - 1)
        self.assertIsNone(characters.show(self.book, "Lise")["character"])
        self.book.set_progress(3, offset=end)
        self.assertIsNotNone(characters.show(self.book, "Lise")["character"])

    def test_first_appearance_not_revealed_when_rewound(self):
        self.book.set_progress(1, offset=0)
        self.assertEqual(characters.show(self.book)["characters"], [])
        self.assertIsNone(characters.show(self.book, "c0001")["character"])

    def test_relationship_and_development_evolve(self):
        characters.record(self.book, "Paul", 3, "Paul est son voisin.", text="Paul is Élise's neighbour.",
                          kind="relationship", target="Élise")
        self.book.set_progress(6, finished=True)
        quote = "Paul est le gardien secret du château."
        characters.record(self.book, "Paul", 6, quote, text="Paul guards the château.", kind="development")
        self.assertEqual(len(characters.show(self.book, "Paul")["character"]["facts"]), 2)
        self.book.set_progress(5, finished=True)
        result = characters.show(self.book, "Paul")
        self.assertEqual(len(result["character"]["facts"]), 1)
        self.assertNotIn("château", json.dumps(result, ensure_ascii=False))

    def test_fact_dedup_preserves_earliest_evidence(self):
        for _ in range(2):
            characters.record(self.book, "Élise", 1, "Élise ferme la porte.", text="She closes the door.")
        self.assertEqual(len(characters.show(self.book, "Élise")["character"]["facts"]), 1)

    def test_uncertain_interpretation_labelled(self):
        characters.record(self.book, "Élise", 1, "Élise ferme la porte.", text="She may want privacy.", certainty="interpretation")
        self.assertEqual(characters.show(self.book, "Élise")["character"]["facts"][0]["certainty"], "interpretation")

    def test_unread_and_invented_evidence_rejected(self):
        for quote, chapter in (("Paul est le gardien secret du château.", 6), ("An invented quote", 1)):
            with self.subTest(quote=quote), self.assertRaises(CompanionError):
                characters.record(self.book, "Paul", chapter, quote, text="Unknown")

    def test_alias_requires_quote_containing_alias(self):
        with self.assertRaises(CompanionError):
            characters.record(self.book, "Élise", 1, "Élise ferme la porte.", alias="Later identity")

    def test_first_name_must_be_in_quote(self):
        with self.assertRaises(CompanionError):
            characters.record(self.book, "Nobody", 1, "Élise ferme la porte.")

    def test_relationship_target_must_be_known(self):
        with self.assertRaises(CompanionError):
            characters.record(self.book, "Élise", 1, "Élise ferme la porte.", text="Knows someone", target="Nobody")

    def test_record_character_cli_and_fresh_process(self):
        self.cli("record-character", "--name", "Élise", "--chapter", "1", "--quote", "Élise ferme la porte.",
                 "--text", "She closes a door.")
        _, result = self.cli("characters", "Élise")
        self.assertEqual(result["result"]["character"]["facts"][0]["text"], "She closes a door.")


if __name__ == "__main__":
    unittest.main()
