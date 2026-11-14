"""Book identity, bounded catalogue pages and persistent reading position.
Uses private JSON indexes and validates chapter paths before reading source files.
"""

import math
from pathlib import Path

from .parsing import digest
from .storage import CompanionError, load, save, timestamp


class Book:
    def __init__(self, store, identifier=None):
        self.path = store.book(identifier)
        self.identifier = self.path.name
        self.index = load(self.path / "index.json")
        self.progress = load(self.path / "progress.json")
        self.chapters = self.index["chapters"]
        if not self.chapters or not isinstance(self.progress.get("chapter"), int):
            raise CompanionError("Invalid book index or progress")
        self.chapter(self.progress["chapter"])
        if not isinstance(self.progress.get("offset"), int) or not 0 <= self.progress["offset"] <= self.chapter(self.progress["chapter"])["characters"]:
            raise CompanionError("Saved progress is outside chapter boundaries")

    def chapter(self, number):
        if not isinstance(number, int) or not 1 <= number <= len(self.chapters):
            raise CompanionError("Chapter number outside book")
        return self.chapters[number - 1]

    def text(self, number):
        chapter = self.chapter(number)
        expected = f"chapters/{number:03d}.md"
        path = self.path / expected
        if chapter["file"] != expected or path.is_symlink() or path.parent.is_symlink():
            raise CompanionError("Unsafe chapter path")
        raw = path.read_bytes()
        if digest(raw) != chapter["sha256"]:
            raise CompanionError("Chapter content changed; original citations cannot be trusted")
        return raw.decode("utf-8")

    def cutoff(self, number, spoilers=False):
        chapter = self.chapter(number)
        if spoilers or number < self.progress["chapter"]:
            return chapter["characters"]
        return self.progress["offset"] if number == self.progress["chapter"] else 0

    def visible(self, number, spoilers=False):
        # Do not open future chapter files at all.
        end = self.cutoff(number, spoilers)
        return self.text(number)[:end] if end else ""

    def known(self, reference, spoilers=False):
        return 0 < reference["end"] <= self.cutoff(reference["chapter"], spoilers)

    def summary(self):
        metadata = load(self.path / "metadata.json")
        return {"book": self.identifier, "title": metadata["title"], "author": metadata["author"],
                "language": metadata["language"], "chapter_count": len(self.chapters), "progress": self.progress}

    def set_progress(self, chapter, offset=None, fraction=None, finished=False, status="reading"):
        info = self.chapter(chapter)
        if sum((offset is not None, fraction is not None, finished)) != 1:
            raise CompanionError("Choose exactly one of --offset, --fraction or --finished")
        if fraction is not None:
            if not math.isfinite(fraction) or not 0 <= fraction <= 1:
                raise CompanionError("Fraction must be between 0 and 1")
            offset = int(info["characters"] * fraction)
        if finished:
            offset = info["characters"]
        if not 0 <= offset <= info["characters"]:
            raise CompanionError("Offset outside chapter")
        if status == "completed" and (chapter != len(self.chapters) or offset != info["characters"]):
            raise CompanionError("Completed status requires finishing the final chapter")
        self.progress = {"chapter": chapter, "offset": offset, "status": status, "updated_at": timestamp()}
        save(self.path / "progress.json", self.progress)
        return {"book": self.identifier, "progress": self.progress}

    def outline(self, offset=0, count=10, spoilers=False):
        if offset < 0 or not 1 <= count <= 20:
            raise CompanionError("Index page requires non-negative offset and count 1..20")
        rows = []
        for chapter in self.chapters[offset:offset + count]:
            row = {"number": chapter["number"], "characters": chapter["characters"]}
            # A title is visible only after its entire heading line has been read.
            visible = self.visible(chapter["number"], spoilers)
            title = chapter["title"]
            position = visible.find(title)
            if position >= 0 and ("\n" in visible[position:] or len(visible) == chapter["characters"]):
                row["title"] = title
            rows.append(row)
        return {"book": self.identifier, "chapters": rows, "page_offset": offset,
                "next_offset": offset + len(rows) if offset + len(rows) < len(self.chapters) else None}


def catalogue(store, offset=0, count=10, status=None):
    if offset < 0 or not 1 <= count <= 20:
        raise CompanionError("Catalogue page requires non-negative offset and count 1..20")
    paths = sorted(p.name for p in store.books.iterdir() if not p.name.startswith(".") and p.is_dir()
                   and (p / "metadata.json").is_file()) if store.books.exists() else []
    rows = []
    for identifier in paths:
        book = Book(store, identifier)
        if status is None or book.progress["status"] == status:
            rows.append(book.summary())
    page = rows[offset:offset + count]
    return {"books": page, "page_offset": offset, "next_offset": offset + len(page) if offset + len(page) < len(rows) else None}


def inbox_files(store, offset=0, count=10):
    if offset < 0 or not 1 <= count <= 20:
        raise CompanionError("Inbox page requires non-negative offset and count 1..20")
    paths = sorted((p for p in store.inbox.iterdir() if not p.is_symlink() and p.is_file()
                    and p.suffix.casefold() in (".md", ".markdown")), key=lambda p: p.name)
    page = [{"name": p.name, "bytes": p.stat().st_size} for p in paths[offset:offset + count]]
    return {"inbox": str(store.inbox), "files": page, "page_offset": offset,
            "next_offset": offset + len(page) if offset + len(page) < len(paths) else None}
