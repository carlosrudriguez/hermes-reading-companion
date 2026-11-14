"""Verify deterministic structure detection, text preservation and safe reindexing.
Runs synthetic multilingual Markdown through real import and CLI entry points.
"""

import unittest

from support import FRENCH, LibraryFixture
from reading_companion.importing import import_book, inspect_plan
from reading_companion.parsing import analyse
from reading_companion.storage import CompanionError, load, save


class ImportTests(LibraryFixture, unittest.TestCase):
    def setUp(self):
        self.setup_library()

    def test_original_and_chapters_byte_exact(self):
        original = self.source.read_bytes()
        self.assertEqual((self.book.path / "original.md").read_bytes(), original)
        combined = b"".join((self.book.path / c["file"]).read_bytes() for c in self.book.chapters)
        self.assertEqual(combined, original)
        self.assertEqual(len(self.book.chapters), 7)

    def test_metadata_not_guessed(self):
        metadata = load(self.book.path / "metadata.json")
        self.assertEqual(metadata["language"], "fr")
        self.assertEqual(metadata["author"], "Auteur fictif")
        path = self.base / "italian.md"
        path.write_text("# Il ponte\n## Capitolo I\nCittà, perché?\n## Capitolo II\nÈ sera.\n", encoding="utf-8")
        import_book(self.store, path, "italian")
        metadata = load(self.store.books / "italian" / "metadata.json")
        self.assertIsNone(metadata["language"])
        self.assertIsNone(metadata["author"])

    def test_nested_parts_preserve_content(self):
        raw = "# Livre\n## Tome I\n### Chapitre I\nUn.\n### Chapitre II\nDeux.\n## Tome II\n### Chapitre I\nTrois.\n".encode()
        plan, text = analyse(raw)
        self.assertFalse(plan["ambiguous"])
        self.assertEqual(len(plan["chapters"]), 3)
        self.assertIn("Tome II", text[plan["chapters"][2]["start"]:])
        self.assertEqual("".join(text[c["start"]:c["end"]] for c in plan["chapters"]).encode(), raw)

    def test_ambiguous_structure_requires_plan_acceptance(self):
        source = self.base / "nested.md"
        source.write_text("# Work\n## First\nA\n### Subsection\nB\n## Second\nC\n### End\nD\n")
        result = import_book(self.store, source, "nested")
        self.assertEqual(result["status"], "review_required")
        self.assertFalse((self.store.books / "nested").exists())
        accepted = import_book(self.store, source, "nested", accept_plan=result["plan_id"])
        self.assertEqual(accepted["status"], "imported")

    def test_changed_plan_cannot_be_accepted(self):
        with self.assertRaises(CompanionError):
            import_book(self.store, self.source, "other", accept_plan="old-plan")

    def test_explicit_level(self):
        plan, _ = analyse(b"# Work\n## One\n### Child\n## Two\n### Child\n", 2)
        self.assertEqual(len(plan["chapters"]), 2)
        self.assertFalse(plan["ambiguous"])

    def test_setext_fences_and_unicode(self):
        raw = "本\n===\n第一章\n---\n東京。\n```md\n# not a heading\n```\n第二章\n---\n終わり。\n".encode()
        plan, _ = analyse(raw)
        self.assertEqual([c["title"] for c in plan["chapters"]], ["第一章", "第二章"])

    def test_plain_labels_need_review(self):
        plan, _ = analyse("CHAPTER I\nUn\nCHAPTER II\nDeux\n".encode())
        self.assertTrue(plan["ambiguous"])
        self.assertEqual(len(plan["chapters"]), 2)

    def test_plain_labels_below_book_title_need_review(self):
        plan, _ = analyse(b"# Work\nCHAPTER I\nOne\nCHAPTER II\nTwo\n")
        self.assertTrue(plan["ambiguous"])
        self.assertEqual(len(plan["chapters"]), 2)

    def test_no_headings_needs_review(self):
        plan, _ = analyse("Texto sem capítulos.".encode())
        self.assertTrue(plan["ambiguous"])

    def test_reindex_retains_progress_and_curated_characters(self):
        self.book.set_progress(3, finished=True)
        curated = {"schema_version": 1, "characters": [{"custom": "preserve me"}]}
        save(self.book.path / "characters.json", curated)
        result = import_book(self.store, self.source, "french", reindex=True)
        self.assertEqual(result["status"], "reindexed")
        self.assertEqual(load(self.book.path / "progress.json")["chapter"], 3)
        self.assertEqual(load(self.book.path / "characters.json"), curated)

    def test_reindex_changed_text_refused_without_data_loss(self):
        before = (self.book.path / "original.md").read_bytes()
        self.source.write_text(FRENCH + "Changed\n", encoding="utf-8")
        with self.assertRaises(CompanionError):
            import_book(self.store, self.source, "french", reindex=True)
        self.assertEqual((self.book.path / "original.md").read_bytes(), before)

    def test_existing_book_not_overwritten(self):
        with self.assertRaises(CompanionError):
            import_book(self.store, self.source, "french")

    def test_malformed_empty_invalid_encoding(self):
        for raw in (b"", b"---\ntitle: unclosed", b"# Title\n```\nOops", b"a\0b", b"\xff"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                analyse(raw)

    def test_crlf_bom_preserved(self):
        raw = "\ufeff# Titre\r\n## Chapitre I\r\nÉté.\r\n## Chapitre II\r\nFin.\r\n".encode()
        plan, text = analyse(raw)
        self.assertEqual("".join(text[c["start"]:c["end"]] for c in plan["chapters"]).encode(), raw)

    def test_plan_pagination(self):
        result = inspect_plan(self.source, offset=2, count=2)
        self.assertEqual([c["number"] for c in result["chapters"]], [3, 4])
        self.assertEqual(result["next_offset"], 4)

    def test_unsafe_book_identifier_rejected(self):
        with self.assertRaises(CompanionError):
            import_book(self.store, self.source, "../escape")

    def test_cli_reindex_default_source(self):
        _, response = self.cli("reindex", "--id", "french")
        self.assertEqual(response["result"]["status"], "reindexed")

    def test_import_by_inbox_filename_and_auto_id(self):
        self.cli("inbox")
        incoming = self.store.inbox / "Mon roman français.md"
        incoming.write_text(FRENCH, encoding="utf-8")
        _, response = self.cli("import", incoming.name)
        self.assertEqual(response["result"]["book"], "mon-roman-français")
        self.assertTrue(incoming.exists())
        self.assertEqual((self.store.books / "mon-roman-français/original.md").read_bytes(), incoming.read_bytes())

    def test_missing_inbox_file_has_actionable_error(self):
        process, response = self.cli("import", "missing.md", check=False)
        self.assertEqual(process.returncode, 1)
        self.assertIn("inbox", response["result"]["error"])

    def test_filename_plan_review_can_be_accepted(self):
        self.cli("inbox")
        incoming = self.store.inbox / "Unusual.md"
        incoming.write_text("No obvious chapters, but still a complete synthetic text.")
        process, response = self.cli("import", incoming.name, check=False)
        self.assertEqual(process.returncode, 2)
        plan_id = response["result"]["plan_id"]
        _, inspected = self.cli("inspect-plan", incoming.name)
        self.assertEqual(inspected["result"]["plan_id"], plan_id)
        _, accepted = self.cli("import", incoming.name, "--accept-plan", plan_id)
        self.assertEqual(accepted["result"]["status"], "imported")

    def test_inbox_filename_symlink_refused(self):
        self.cli("inbox")
        (self.store.inbox / "linked.md").symlink_to(self.source)
        process, response = self.cli("import", "linked.md", check=False)
        self.assertEqual(process.returncode, 1)
        self.assertIn("symlink", response["result"]["error"])


if __name__ == "__main__":
    unittest.main()
