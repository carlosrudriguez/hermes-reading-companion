"""Command-line interface for bounded, spoiler-aware library operations.
Uses argparse and the companion's standard-library modules; prints JSON only.
"""

import argparse
import sys

from . import characters
from .importing import import_book, inspect_plan, resolve_source
from .library import Book, catalogue, inbox_files
from .retrieval import passage, search
from .storage import CompanionError, Store, bounded_response


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        raise CompanionError("Invalid command arguments; use --help for accepted syntax")


def parser():
    root = SafeParser(description="Local reading tools; bounded JSON output")
    root.add_argument("--home", help="Private library home (or READING_COMPANION_HOME)")
    root.add_argument("--max-bytes", type=int, help="Response budget: 1024..16000 UTF-8 bytes")
    commands = root.add_subparsers(dest="command", required=True)
    command = commands.add_parser("inbox", help="Show the upload folder and available Markdown filenames, without reading them")
    command.add_argument("--offset", type=int, default=0)
    command.add_argument("--count", type=int, default=10)
    for name in ("import", "reindex", "inspect-plan"):
        command = commands.add_parser(name)
        command.add_argument("source", nargs="?" if name == "reindex" else None)
        command.add_argument("--heading-level", type=int, choices=range(1, 7))
        if name != "inspect-plan":
            command.add_argument("--id")
            command.add_argument("--title")
            command.add_argument("--author")
            command.add_argument("--language")
            command.add_argument("--accept-plan")
            command.add_argument("--review", action="store_true")
        else:
            command.add_argument("--offset", type=int, default=0)
            command.add_argument("--count", type=int, default=10)
    command = commands.add_parser("list")
    command.add_argument("--status", choices=("not_started", "reading", "paused", "completed"))
    command.add_argument("--offset", type=int, default=0)
    command.add_argument("--count", type=int, default=10)
    command = commands.add_parser("select")
    command.add_argument("identifier")
    for name in ("inspect", "index", "progress", "passage", "search", "characters", "record-character"):
        command = commands.add_parser(name)
        command.add_argument("--book")
        if name in ("index", "passage", "search", "characters"):
            command.add_argument("--allow-spoilers", action="store_true", help="Only after explicit user authorisation")
        if name in ("index", "characters"):
            command.add_argument("--offset", type=int, default=0)
            command.add_argument("--count", type=int, default=5)
        if name == "progress":
            command.add_argument("--chapter", type=int)
            position = command.add_mutually_exclusive_group()
            position.add_argument("--offset", type=int)
            position.add_argument("--fraction", type=float)
            position.add_argument("--finished", action="store_true")
            command.add_argument("--status", choices=("not_started", "reading", "paused", "completed"), default="reading")
        if name == "passage":
            command.add_argument("--chapter", type=int, required=True)
            command.add_argument("--start", type=int, default=0)
            command.add_argument("--length", type=int, default=1200)
            command.add_argument("--purpose", choices=("explain", "literal-translation", "idiomatic-translation", "grammar", "analysis"), default="explain")
        if name == "search":
            command.add_argument("query")
            command.add_argument("--chapter", type=int)
            command.add_argument("--count", type=int, default=5)
            command.add_argument("--cursor")
        if name == "characters":
            command.add_argument("query", nargs="?")
        if name == "record-character":
            command.add_argument("--name", required=True, help="Known name or character ID")
            command.add_argument("--chapter", type=int, required=True)
            command.add_argument("--quote", required=True)
            command.add_argument("--start", type=int)
            command.add_argument("--alias")
            command.add_argument("--text")
            command.add_argument("--kind", choices=("description", "relationship", "development"), default="description")
            command.add_argument("--certainty", choices=("verified", "interpretation"), default="verified")
            command.add_argument("--target")
    return root


def dispatch(store, args):
    name = args.command
    if name == "inbox":
        return inbox_files(store, args.offset, args.count)
    if name == "list":
        return catalogue(store, args.offset, args.count, args.status)
    if name == "select":
        return store.select(args.identifier)
    if name == "inspect-plan":
        return inspect_plan(resolve_source(store, args.source), args.heading_level, args.offset, args.count)
    if name in ("import", "reindex"):
        source, level = args.source, args.heading_level
        if name == "reindex" and source is None:
            path = store.book(args.id)
            source = path / "original.md"
            from .storage import load
            metadata = load(path / "metadata.json")
            args.id = path.name
            level = metadata["heading_level"] if level is None else level
            if not args.accept_plan:
                args.accept_plan = metadata["accepted_plan"]
        return import_book(store, source, args.id, args.title, args.author, args.language,
                           level, args.accept_plan, args.review, name == "reindex")
    book = Book(store, args.book)
    if name == "inspect":
        return book.summary()
    if name == "progress":
        if args.chapter is None:
            if args.offset is not None or args.fraction is not None or args.finished:
                raise CompanionError("--chapter is required when setting progress")
            return {"book": book.identifier, "progress": book.progress}
        return book.set_progress(args.chapter, args.offset, args.fraction, args.finished, args.status)
    if name == "index":
        return book.outline(args.offset, args.count, args.allow_spoilers)
    if name == "passage":
        return passage(book, args.chapter, args.start, args.length, args.allow_spoilers, args.purpose)
    if name == "search":
        return search(book, args.query, args.chapter, args.count, args.cursor, args.allow_spoilers)
    if name == "characters":
        return characters.show(book, args.query, args.allow_spoilers, args.offset, args.count)
    if name == "record-character":
        return characters.record(book, args.name, args.chapter, args.quote, args.start,
                                 args.alias, args.text, args.kind, args.certainty, args.target)
    raise CompanionError("Unknown operation")


def main(argv=None):
    limit, exit_code = 6000, 0
    try:
        args = parser().parse_args(argv)
        store = Store(args.home)
        with store.locked():
            limit = store.limit(args.max_bytes)
            result = dispatch(store, args)
            if result.get("status") == "review_required":
                exit_code = 2
    except (CompanionError, OSError, ValueError, KeyError, TypeError, IndexError) as error:
        # Do not echo source text, JSON contents, credentials or arbitrary filenames.
        message = str(error) if isinstance(error, CompanionError) else f"Invalid or unavailable data ({type(error).__name__}); inspect local files"
        result, exit_code = {"error": message[:500]}, 1
    sys.stdout.write(bounded_response(result, limit))
    return exit_code
