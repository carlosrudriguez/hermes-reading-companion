"""Deterministic Markdown structure detection without model calls.
Preserves byte-exact UTF-8 source via character offsets and hashlib checks.
"""

import hashlib
import re

CHAPTER = re.compile(r"^(?:chapter|chapitre|cap[ií]tulo|capitolo|kapitel|hoofdstuk|глава|第.{1,15}[章回節])(?:\b|\s|$)", re.I)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def analyse(raw, heading_level=None):
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("Book must be UTF-8 Markdown; convert its encoding before import") from None
    if not text.strip() or "\x00" in text:
        raise ValueError("Book is empty or contains NUL bytes")
    lines = text.splitlines(keepends=True)
    metadata = {}
    front_end = 0
    if lines[0].lstrip("\ufeff").strip() == "---":
        for i, line in enumerate(lines[1:], 1):
            if line.strip() in ("---", "..."):
                front_end = i + 1
                break
        if not front_end:
            raise ValueError("Unclosed Markdown frontmatter")
        for line in lines[1:front_end - 1]:
            match = re.match(r"^(title|author|language|lang):\s*(.+?)\s*$", line)
            if match:
                metadata[match[1]] = match[2].strip("\"'")[:300]
    headings, plain = [], []
    offset, fence = 0, None
    for i, line in enumerate(lines):
        clean = line.strip().lstrip("\ufeff")
        if i < front_end:
            offset += len(line)
            continue
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if marker:
            token = marker[1]
            if fence is None:
                fence = (token[0], len(token))
            elif token[0] == fence[0] and len(token) >= fence[1]:
                fence = None
            offset += len(line)
            continue
        if fence is None:
            atx = re.match(r"^ {0,3}(#{1,6})\s+(.+?)\s*#*\s*$", clean)
            if atx:
                headings.append({"level": len(atx[1]), "title": atx[2][:300], "start": offset})
            elif (clean and i + 1 < len(lines) and re.fullmatch(r" {0,3}(?:=+|-+)\s*", lines[i + 1].rstrip("\r\n"))):
                headings.append({"level": 1 if "=" in lines[i + 1] else 2, "title": clean[:300], "start": offset})
            elif CHAPTER.match(clean) and len(clean) < 160:
                plain.append({"level": 0, "title": clean, "start": offset})
        offset += len(line)
    if fence is not None:
        raise ValueError("Unclosed Markdown code fence; repair source before import")
    if not metadata.get("title") and headings and not CHAPTER.match(headings[0]["title"]):
        metadata["title"] = headings[0]["title"]
    reasons = []
    if heading_level is not None:
        selected = [h for h in headings if h["level"] == heading_level]
        if not selected:
            raise ValueError("Requested heading level has no headings")
    else:
        named = [h for h in headings if CHAPTER.match(h["title"])]
        candidates = named or ([] if plain else headings)
        if not named and len(headings) > 1 and headings[0]["level"] < min(h["level"] for h in headings[1:]):
            candidates = headings[1:]
        if candidates:
            levels = {h["level"] for h in candidates}
            if len(levels) > 1:
                reasons.append("Mixed or nested heading levels; review proposed leaf-level splitting")
            level = max(levels)
            selected = [h for h in candidates if h["level"] == level]
            if len(selected) == 1 and not named:
                reasons.append("Only one structural heading; review the proposed single text unit")
        elif plain:
            selected = plain
            reasons.append("Plain-text chapter labels need review")
        else:
            selected = [{"level": 0, "title": metadata.get("title", "Text"), "start": 0}]
            reasons.append("No reliable chapter boundaries; proposed single text unit needs review")
    # Attach intervening part/volume headings to the next chapter, preserving all text.
    selected = [dict(h) for h in selected]
    for i, heading in enumerate(selected):
        previous = selected[i - 1]["heading_start"] if i else -1
        heading["heading_start"] = heading["start"]
        parents = [h for h in headings if previous < h["start"] < heading["start"] and h["level"] < heading["level"]]
        heading["parents"] = [h["title"] for h in parents]
        if parents:
            heading["start"] = min(p["start"] for p in parents)
    selected[0]["start"] = 0
    chapters = []
    for i, heading in enumerate(selected):
        start = heading["start"]
        end = selected[i + 1]["start"] if i + 1 < len(selected) else len(text)
        chapter = text[start:end]
        chapters.append({"number": i + 1, "title": heading["title"], "parents": heading["parents"],
                         "file": f"chapters/{i + 1:03d}.md", "start": start, "end": end,
                         "characters": len(chapter), "bytes": len(chapter.encode("utf-8")),
                         "sha256": digest(chapter.encode("utf-8"))})
    plan_id = digest((digest(raw) + str([(c["start"], c["end"]) for c in chapters])).encode())[:20]
    return {"metadata": metadata, "chapters": chapters, "ambiguous": bool(reasons),
            "reasons": reasons, "plan_id": plan_id, "sha256": digest(raw)}, text
