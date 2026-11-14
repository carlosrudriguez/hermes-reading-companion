"""Spoiler-filtered, paged passages and literal Unicode text search.
Reads chapter files through Book; never opens the preserved original book.
"""

import re

from .storage import CompanionError, short

MAX_PASSAGE = 2400
DEFAULT_PASSAGE = 1200


def citation(book, chapter, text, start, end):
    return {"book": book.identifier, "chapter": chapter, "start": start, "end": end,
            "line": text.count("\n", 0, start) + 1,
            "end_line": text.count("\n", 0, max(start, end - 1)) + 1}


def passage(book, chapter, start=0, length=DEFAULT_PASSAGE, spoilers=False, purpose="explain"):
    if start < 0 or not 1 <= length <= MAX_PASSAGE:
        raise CompanionError("Passage needs non-negative start and length 1..2400")
    text = book.visible(chapter, spoilers)
    if len(book.chapters) == 1:
        length = min(length, max(0, book.chapter(1)["characters"] // 2))
    end = min(len(text), start + length)
    if start >= len(text) or not length:
        return {"book": book.identifier, "chapter": chapter, "text": "", "blocked": True,
                "reason": "No text available at this offset within your saved reading position"}
    return {**citation(book, chapter, text, start, end), "text": text[start:end],
            "next_offset": end if end < len(text) else None, "purpose": purpose,
            "spoiler_override": spoilers}


def search(book, query, chapter=None, count=5, cursor=None, spoilers=False):
    short(query, 200)
    if not query.strip() or not 1 <= count <= 10:
        raise CompanionError("Search requires non-empty query and count 1..10")
    if chapter is not None:
        book.chapter(chapter)
    first, offset = (chapter or 1), 0
    if cursor:
        try:
            first, offset = map(int, cursor.split(":"))
        except ValueError:
            raise CompanionError("Search cursor must be chapter:offset") from None
        book.chapter(first)
        if offset < 0 or (chapter is not None and first != chapter):
            raise CompanionError("Cursor does not belong to requested chapter")
    rows, files, scanned = [], 0, 0
    # Even a tiny one-chapter book cannot be emitted in full by one search.
    excerpt_budget = min(400, max(0, (sum(c["characters"] for c in book.chapters) - 1) // count))
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    last = chapter or len(book.chapters)
    next_cursor = None
    for number in range(first, last + 1):
        text = book.visible(number, spoilers)
        if text:
            files += 1
            scanned += len(text.encode("utf-8"))
        for match in pattern.finditer(text, offset if number == first else 0):
            radius = min(100, max(1, book.chapter(number)["characters"] // 24))
            start = max(0, match.start() - radius)
            end = min(len(text), match.end() + radius)
            end = min(end, start + excerpt_budget)
            if end <= start:
                continue
            rows.append({**citation(book, number, text, start, end), "text": text[start:end],
                         "match_start": match.start(), "match_end": match.end()})
            if len(rows) == count:
                next_cursor = f"{number}:{match.end()}"
                break
        if len(rows) == count:
            break
    return {"book": book.identifier, "matches": rows, "next_cursor": next_cursor,
            "chapter_files_scanned": files, "visible_bytes_scanned_locally": scanned,
            "spoiler_override": spoilers,
            "notice": "No later text was searched unless explicitly authorised"}
