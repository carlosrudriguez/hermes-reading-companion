"""Verify bounded output, chapter-only access and exact spoiler cutoffs.
Exercises Python retrieval and fresh CLI processes using synthetic books.
"""

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from support import FRENCH, LibraryFixture
from reading_companion.importing import import_book
from reading_companion.library import Book
from reading_companion.retrieval import passage, search
from reading_companion.storage import CompanionError, bounded_response, save


class RetrievalTests(LibraryFixture, unittest.TestCase):
    def setUp(self):
        self.setup_library()

    def test_starting_chapter_hides_entire_current_chapter(self):
        self.book.set_progress(5, offset=0)
        self.assertTrue(passage(self.book, 5)["blocked"])
        self.assertEqual(search(self.book, "corde")["matches"], [])

    def test_finished_chapter_excludes_future_search(self):
        self.book.set_progress(5, finished=True)
        result = search(self.book, "corde")
        self.assertTrue(result["matches"])
        self.assertEqual(search(self.book, "RÉVÉLATION_ZÈBRE")["matches"], [])
        self.assertNotIn("RÉVÉLATION", json.dumps(self.book.outline(), ensure_ascii=False))

    def test_half_chapter_cutoff_inside_line(self):
        self.book.set_progress(5, fraction=0.5)
        visible = self.book.visible(5)
        self.assertEqual(len(visible), self.book.chapter(5)["characters"] // 2)
        result = passage(self.book, 5)
        self.assertEqual(result["text"], visible)
        self.assertLessEqual(result["end"], self.book.progress["offset"])

    def test_spoiler_override_is_explicit_and_does_not_change_progress(self):
        before = dict(self.book.progress)
        self.assertTrue(search(self.book, "RÉVÉLATION_ZÈBRE", spoilers=True)["matches"])
        self.assertEqual(self.book.progress, before)

    def test_question_chapter_five_reads_only_chapter_five(self):
        self.book.set_progress(5, finished=True)
        reads, original = [], Path.read_bytes

        def audit(path):
            reads.append(str(path))
            return original(path)

        with patch.object(Path, "read_bytes", audit):
            result = search(self.book, "corde", chapter=5)
            excerpt = passage(self.book, 5)
        self.assertEqual(result["chapter_files_scanned"], 1)
        self.assertTrue(excerpt["text"])
        self.assertTrue(all(p.endswith("chapters/005.md") for p in reads))
        self.assertFalse(any(p.endswith("original.md") for p in reads))

    def test_future_chapter_file_not_opened(self):
        with patch.object(Path, "read_bytes", side_effect=AssertionError("must not open future file")):
            self.assertTrue(passage(self.book, 6)["blocked"])

    def test_independent_multiple_books(self):
        other = self.base / "spanish.md"
        other.write_text("# Libro\n## Capítulo I\nHola.\n## Capítulo II\nAdiós.\n")
        import_book(self.store, other, "spanish")
        self.book.set_progress(5, finished=True)
        self.store.select("spanish")
        second = Book(self.store)
        self.assertEqual(second.progress["offset"], 0)
        self.assertEqual(Book(self.store, "french").progress["chapter"], 5)

    def test_inbox_is_not_listed_as_an_imported_book(self):
        inbox = self.store.books / "inbox"
        inbox.mkdir(exist_ok=True)
        (inbox / "incoming.md").write_text("Not imported")
        _, response = self.cli("list")
        self.assertEqual([b["book"] for b in response["result"]["books"]], ["french"])

    def test_inbox_lists_filenames_and_sizes_without_reading_contents(self):
        with self.store.locked():
            path = self.store.inbox / "Été avec des espaces.MD"
            path.write_text("PRIVATE_SOURCE_TEXT", encoding="utf-8")
            (self.store.inbox / "notes.txt").write_text("not a book")
            (self.store.inbox / "linked.md").symlink_to(path)
        from reading_companion.library import inbox_files
        with patch.object(Path, "read_bytes", side_effect=AssertionError("No content reads")), \
             patch.object(Path, "read_text", side_effect=AssertionError("No content reads")):
            result = inbox_files(self.store)
        self.assertEqual(result["files"], [{"name": path.name, "bytes": path.stat().st_size}])
        self.assertNotIn("PRIVATE_SOURCE_TEXT", json.dumps(result))

    def test_inbox_cli_initialises_and_pages(self):
        self.cli("inbox")
        for name in ("A.md", "B.markdown", "C.MD"):
            (self.store.inbox / name).write_text("not opened")
        _, response = self.cli("inbox", "--offset", "1", "--count", "1")
        self.assertEqual(response["result"]["files"][0]["name"], "B.markdown")
        self.assertEqual(response["result"]["next_offset"], 2)

    def test_new_process_retains_selection_and_progress(self):
        self.cli("progress", "--chapter", "5", "--finished")
        _, response = self.cli("inspect")
        self.assertEqual(response["result"]["book"], "french")
        self.assertEqual(response["result"]["progress"]["chapter"], 5)

    def test_translation_workflow_returns_exact_original_and_reference(self):
        self.book.set_progress(5, finished=True)
        source = self.book.text(5)
        start = source.index("La corde est solide.")
        for purpose in ("literal-translation", "idiomatic-translation", "grammar", "analysis"):
            result = passage(self.book, 5, start, len("La corde est solide."), purpose=purpose)
            self.assertEqual(result["text"], "La corde est solide.")
            self.assertEqual(result["chapter"], 5)
            self.assertEqual(result["purpose"], purpose)

    def test_utf8_output_limits_include_json_overhead(self):
        for limit in (1024, 2000, 6000, 16000):
            encoded = bounded_response({"text": "你好🌳é\n" * 50000, "chapter": 1, "start": 0, "end": 250000}, limit)
            response = json.loads(encoded)
            self.assertLessEqual(len(encoded.encode()), limit)
            self.assertEqual(response["metrics"]["output_bytes"], len(encoded.encode()))
            self.assertTrue(response["metrics"]["truncated"])
            self.assertEqual(response["result"]["end"], len(response["result"]["text"]))

    def test_actual_cli_caps_long_multibyte_passage(self):
        source = self.base / "unicode.md"
        source.write_text("# Work\n## Chapter I\n" + "你好🌳" * 4000 + "\n## Chapter II\nFin\n", encoding="utf-8")
        import_book(self.store, source, "unicode")
        book = Book(self.store, "unicode")
        book.set_progress(1, finished=True)
        process, response = self.cli("--max-bytes", "1024", "passage", "--book", "unicode", "--chapter", "1", "--length", "2400")
        self.assertLessEqual(len(process.stdout.encode()), 1024)
        self.assertTrue(response["metrics"]["truncated"])
        result = response["result"]
        self.assertEqual(result["text"], book.text(1)[result["start"]:result["end"]])

    def test_nested_character_pages_keep_valid_next_offset(self):
        value = {"character": {"id": "c0001", "name": "Élise", "facts": [
            {"text": "é" * 200, "evidence": {"chapter": i}} for i in range(10)],
            "aliases": [], "page_offset": 0, "next_offset": None}}
        response = json.loads(bounded_response(value, 1024))
        character = response["result"]["character"]
        self.assertEqual(character["next_offset"], len(character["facts"]))

    def test_paged_index_survives_truncation_without_skipping(self):
        rows = [{"number": i, "title": "É" * 300} for i in range(20)]
        encoded = bounded_response({"chapters": rows, "page_offset": 0, "next_offset": 20}, 1024)
        result = json.loads(encoded)["result"]
        self.assertEqual(result["next_offset"], len(result["chapters"]))

    def test_search_case_insensitive_and_literal(self):
        self.book.set_progress(5, finished=True)
        self.assertTrue(search(self.book, "ÉLISE")["matches"])
        self.assertEqual(search(self.book, ".*")["matches"], [])

    def test_search_cursor(self):
        self.book.set_progress(5, finished=True)
        result = search(self.book, "Élise", count=1)
        second = search(self.book, "Élise", count=1, cursor=result["next_cursor"])
        self.assertGreaterEqual(second["matches"][0]["chapter"], result["matches"][0]["chapter"])
        self.assertNotEqual(second["matches"][0], result["matches"][0])

    def test_future_title_and_partial_heading_hidden(self):
        self.book.set_progress(5, offset=4)
        result = self.book.outline(offset=4, count=3)
        self.assertTrue(all("title" not in row for row in result["chapters"]))

    def test_missing_and_tampered_chapter(self):
        self.book.set_progress(5, finished=True)
        path = self.book.path / "chapters/005.md"
        path.write_text("tampered")
        with self.assertRaises(CompanionError):
            passage(self.book, 5)
        path.unlink()
        process, result = self.cli("passage", "--chapter", "5", check=False)
        self.assertEqual(process.returncode, 1)
        self.assertIn("error", result["result"])

    def test_bad_json_and_unsafe_paths(self):
        (self.book.path / "progress.json").write_text("{broken")
        process, result = self.cli("inspect", check=False)
        self.assertEqual(process.returncode, 1)
        self.assertIn("Invalid JSON", result["result"]["error"])
        with self.assertRaises(CompanionError):
            self.store.book("../escape")

    def test_cli_error_paths_and_hard_limit(self):
        cases = [("--max-bytes", "999999", "inspect"), ("passage", "--chapter", "99"),
                 ("passage", "--chapter", "1", "--length", "99999"),
                 ("progress", "--chapter", "1", "--fraction", "nan"),
                 ("search", "x", "--cursor", "-1:0"), ("--unknown", "x" * 20000)]
        for args in cases:
            with self.subTest(args=args[:3]):
                process, result = self.cli(*args, check=False)
                self.assertEqual(process.returncode, 1)
                self.assertLessEqual(len(process.stdout.encode()), 6000)
                self.assertEqual(process.stderr, "")

    def test_single_unit_never_returned_as_whole_book(self):
        source = self.base / "single.md"
        source.write_text("# Only\nA short tale with a key.\n")
        imported = import_book(self.store, source, "single")
        if imported["status"] == "review_required":
            import_book(self.store, source, "single", accept_plan=imported["plan_id"])
        book = Book(self.store, "single")
        book.set_progress(1, finished=True)
        self.assertLess(len(passage(book, 1)["text"]), len(source.read_text()))


if __name__ == "__main__":
    unittest.main()
