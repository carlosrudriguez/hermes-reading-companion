"""Transactional book import and conservative state-preserving reindex.
Uses deterministic parsing, staging directories and atomic filesystem rename.
"""

import os
import re
import shutil
import tempfile
from pathlib import Path

from .parsing import analyse, digest
from .storage import CompanionError, load, save, short, timestamp


def resolve_source(store, source):
    path = Path(source).expanduser()
    if not path.is_absolute() and path.parent == Path("."):
        incoming = store.inbox / path.name
        if incoming.is_symlink():
            raise CompanionError("Inbox entries must be actual Markdown files, not symlinks")
        if incoming.is_file():
            return incoming
    if not path.is_file():
        raise CompanionError("Book file not found; place it in the inbox and use its filename, or give its full path")
    return path


def import_book(store, source, identifier=None, title=None, author=None, language=None,
                heading_level=None, accept_plan=None, review=False, reindex=False):
    source = resolve_source(store, source)
    raw = source.read_bytes()
    try:
        plan, text = analyse(raw, heading_level)
    except ValueError as error:
        raise CompanionError(str(error)) from None
    identifier = identifier or re.sub(r"[^\w-]+", "-", source.stem.lower(), flags=re.UNICODE).strip("-")[:100]
    if identifier == "inbox":
        raise CompanionError("The book ID inbox is reserved for incoming files; choose another --id")
    if not re.fullmatch(r"[\w-]{1,100}", identifier):
        raise CompanionError("Provide a safe --id containing letters, numbers, underscores or hyphens")
    if accept_plan and accept_plan != plan["plan_id"]:
        raise CompanionError("Import plan changed; review the current plan before accepting")
    if review or (plan["ambiguous"] and accept_plan != plan["plan_id"]):
        return {"status": "review_required", "book": identifier, "plan_id": plan["plan_id"],
                "reasons": plan["reasons"], "chapter_count": len(plan["chapters"]),
                "chapters": [{"number": c["number"], "title": c["title"], "characters": c["characters"]} for c in plan["chapters"]],
                "instruction": "Review all pages using inspect-plan, then repeat with --accept-plan PLAN_ID"}
    destination = store.books / identifier
    if destination.is_symlink():
        raise CompanionError("Refusing symlink book directory")
    existing = destination.exists()
    if existing and not reindex:
        raise CompanionError("Book already exists; use reindex to preserve its state")
    old_meta = load(destination / "metadata.json") if existing else {}
    if existing:
        old_index = load(destination / "index.json")
        if old_meta.get("sha256") != plan["sha256"] or [c["sha256"] for c in old_index["chapters"]] != [c["sha256"] for c in plan["chapters"]]:
            raise CompanionError("Reindex would invalidate progress or citations; import changed text as a new book ID")
    metadata = dict(old_meta or plan["metadata"])
    for key, value in (("title", title), ("author", author), ("language", language)):
        if value is not None:
            metadata[key] = short(value)
    metadata.setdefault("title", source.stem[:300])
    metadata.setdefault("author", None)
    metadata.setdefault("language", plan["metadata"].get("lang"))
    metadata.update({"schema_version": 1, "id": identifier, "sha256": plan["sha256"], "bytes": len(raw),
                     "chapter_count": len(plan["chapters"]), "indexed_at": timestamp(),
                     "heading_level": heading_level, "accepted_plan": plan["plan_id"]})
    store.books.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".import-", dir=store.books))
    backup = store.books / f".reindex-{identifier}"
    try:
        if backup.exists():
            raise CompanionError("Interrupted reindex backup exists; recover it before reindexing")
        (staging / "chapters").mkdir()
        (staging / "original.md").write_bytes(raw)
        reconstructed = bytearray()
        for chapter in plan["chapters"]:
            chunk = text[chapter["start"]:chapter["end"]].encode("utf-8")
            (staging / chapter["file"]).write_bytes(chunk)
            reconstructed.extend(chunk)
        if bytes(reconstructed) != raw or digest(reconstructed) != plan["sha256"]:
            raise CompanionError("Text preservation validation failed")
        save(staging / "metadata.json", metadata)
        save(staging / "index.json", {"schema_version": 1, "sha256": plan["sha256"], "chapters": plan["chapters"]})
        for name, default in (("characters.json", {"schema_version": 1, "characters": []}),
                              ("progress.json", {"chapter": 1, "offset": 0, "status": "not_started", "updated_at": timestamp()})):
            save(staging / name, load(destination / name) if existing else default)
        if existing:
            os.replace(destination, backup)
        try:
            os.replace(staging, destination)
        except OSError:
            if existing:
                os.replace(backup, destination)
            raise
        if existing:
            shutil.rmtree(backup)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return {"status": "reindexed" if existing else "imported", "book": identifier,
            "chapter_count": len(plan["chapters"]), "preserved_bytes": len(raw), "sha256": plan["sha256"]}


def inspect_plan(source, heading_level=None, offset=0, count=10):
    try:
        plan, _ = analyse(Path(source).expanduser().read_bytes(), heading_level)
    except ValueError as error:
        raise CompanionError(str(error)) from None
    if offset < 0 or not 1 <= count <= 20:
        raise CompanionError("Plan page requires non-negative offset and count 1..20")
    chapters = plan["chapters"][offset:offset + count]
    return {"plan_id": plan["plan_id"], "chapter_count": len(plan["chapters"]), "reasons": plan["reasons"],
            "chapters": [{k: c[k] for k in ("number", "title", "parents", "characters")} for c in chapters],
            "next_offset": offset + len(chapters) if offset + len(chapters) < len(plan["chapters"]) else None}
