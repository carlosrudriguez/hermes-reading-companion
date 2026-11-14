"""Incremental character assertions grounded in exact, already-read quotations.
Filters every name, alias, relationship and fact using Book's saved cutoff.
"""

import unicodedata

from .storage import CompanionError, load, save, short


def normalise(name):
    return unicodedata.normalize("NFC", name).casefold().strip()


def evidence(book, chapter, quote, start=None):
    short(quote, 400)
    if not quote.strip():
        raise CompanionError("An exact source quotation is required")
    text = book.visible(chapter)
    if start is None:
        if text.count(quote) != 1:
            raise CompanionError("Quotation is absent or repeated; supply its exact --start offset")
        start = text.index(quote)
    if start < 0 or text[start:start + len(quote)] != quote:
        raise CompanionError("Quotation is not present at this already-read offset")
    return {"chapter": chapter, "start": start, "end": start + len(quote), "quote": quote}


def read_index(book):
    return load(book.path / "characters.json")["characters"]


def visible_character(book, character, spoilers=False):
    if not book.known(character["introduced"], spoilers):
        return None
    return {"id": character["id"], "name": character["name"], "first_appearance": character["introduced"],
            "aliases": [a for a in character["aliases"] if book.known(a["evidence"], spoilers)],
            "facts": [f for f in character["facts"] if book.known(f.get("known_at", f["evidence"]), spoilers)]}


def find_visible(book, rows, query, spoilers=False):
    query = normalise(query)
    candidates = []
    for row in rows:
        visible = visible_character(book, row, spoilers)
        if visible and query in {normalise(row["id"]), normalise(row["name"]), *(normalise(a["name"]) for a in visible["aliases"])}:
            candidates.append(row)
    if len(candidates) > 1:
        raise CompanionError("Ambiguous name or alias; use a character ID")
    return candidates[0] if candidates else None


def show(book, query=None, spoilers=False, offset=0, count=5):
    if offset < 0 or not 1 <= count <= 10:
        raise CompanionError("Character page requires non-negative offset and count 1..10")
    rows = read_index(book)
    if query:
        character = find_visible(book, rows, query, spoilers)
        visible = visible_character(book, character, spoilers) if character else None
        # Keep pages bounded even when one character has thousands of facts.
        if visible:
            facts, aliases = visible["facts"], visible["aliases"]
            visible["facts"] = facts[offset:offset + count]
            visible["aliases"] = aliases[offset:offset + count]
            visible["page_offset"] = offset
            visible["next_offset"] = offset + count if max(len(facts), len(aliases)) > offset + count else None
        return {"character": visible, "notice": "Only indexed information available at this reading position is returned"}
    known = [visible_character(book, c, spoilers) for c in rows]
    known = [c for c in known if c]
    page = [{"id": c["id"], "name": c["name"]} for c in known[offset:offset + count]]
    return {"characters": page, "page_offset": offset,
            "next_offset": offset + len(page) if offset + len(page) < len(known) else None}


def record(book, name, chapter, quote, start=None, alias=None, text=None, kind="description",
           certainty="verified", target=None):
    name = short(name, 120)
    reference = evidence(book, chapter, quote, start)
    rows = read_index(book)
    character = find_visible(book, rows, name)
    if character is None:
        if alias or text or target:
            raise CompanionError("Record the character's first appearance before adding aliases or facts")
        if normalise(name) not in normalise(quote):
            raise CompanionError("First-appearance quotation must contain the character's name")
        if any(normalise(c["name"]) == normalise(name) for c in rows):
            raise CompanionError("Character not available at this reading position")
        character = {"id": f"c{len(rows) + 1:04d}", "name": name, "introduced": reference, "aliases": [], "facts": []}
        rows.append(character)
    if alias:
        alias = short(alias, 120)
        if normalise(alias) not in normalise(quote):
            raise CompanionError("Alias quotation must contain the alias")
        existing = find_visible(book, rows, alias)
        if existing and existing["id"] != character["id"]:
            raise CompanionError("Alias already identifies another character")
        if not any(normalise(a["name"]) == normalise(alias) and a["evidence"] == reference for a in character["aliases"]):
            character["aliases"].append({"name": alias, "evidence": reference})
    if text:
        if kind not in ("description", "relationship", "development") or certainty not in ("verified", "interpretation"):
            raise CompanionError("Unknown fact kind or certainty")
        item = {"text": short(text, 500), "kind": kind, "certainty": certainty, "evidence": reference}
        if target:
            related = find_visible(book, rows, target)
            if not related:
                raise CompanionError("Relationship target is not indexed at the saved reading position")
            item["target"] = related["id"]
            item["known_at"] = max((reference, related["introduced"]), key=lambda r: (r["chapter"], r["end"]))
        duplicate = next((f for f in character["facts"] if normalise(f["text"]) == normalise(text) and f["kind"] == kind and f.get("target") == item.get("target")), None)
        if duplicate:
            # Do not move an early fact's availability forward on repeated mention.
            if (reference["chapter"], reference["end"]) < (duplicate["evidence"]["chapter"], duplicate["evidence"]["end"]):
                duplicate["evidence"] = reference
            duplicate["certainty"] = certainty
        else:
            character["facts"].append(item)
    save(book.path / "characters.json", {"schema_version": 1, "characters": rows})
    return {"recorded": character["id"], "evidence": reference}
