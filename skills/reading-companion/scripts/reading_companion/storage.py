"""Private filesystem storage, atomic writes and operation locking.
Uses pathlib, JSON and POSIX flock on the supported macOS/Linux targets.
"""

import contextlib
import fcntl
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HARD_OUTPUT_BYTES = 16000
DEFAULT_OUTPUT_BYTES = 6000


class CompanionError(Exception):
    """A safe, actionable error suitable for bounded CLI output."""


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def load(path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        if default is not None:
            return default
        raise CompanionError(f"Missing required file: {path.name}") from None
    except (ValueError, UnicodeError):
        raise CompanionError(f"Invalid JSON or encoding: {path.name}") from None


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def short(value, maximum=300):
    value = str(value)
    if len(value) > maximum or "\x00" in value:
        raise CompanionError(f"Field exceeds {maximum} characters or contains NUL")
    return value


class Store:
    def __init__(self, home=None):
        base = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
        self.home = Path(home or os.environ.get("READING_COMPANION_HOME", base / "reading-companion")).expanduser().resolve()
        self.books = self.home / "books"
        self.inbox = self.books / "inbox"

    @contextlib.contextmanager
    def locked(self):
        self.home.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.books.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.inbox.mkdir(parents=True, exist_ok=True, mode=0o700)
        with (self.home / ".lock").open("a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def config(self):
        value = load(self.home / "config.json", {})
        if not isinstance(value, dict):
            raise CompanionError("config.json must contain an object")
        return value

    def limit(self, requested=None):
        value = requested if requested is not None else self.config().get("output_bytes", DEFAULT_OUTPUT_BYTES)
        if not isinstance(value, int) or not 1024 <= value <= HARD_OUTPUT_BYTES:
            raise CompanionError("Output limit must be between 1024 and 16000 bytes")
        return value

    def book(self, identifier=None):
        identifier = identifier or load(self.home / "state.json", {}).get("active_book")
        if not identifier or not re.fullmatch(r"[\w-]{1,100}", identifier, re.UNICODE):
            raise CompanionError("Select a book first, or provide a valid --book identifier")
        path = self.books / identifier
        if path.is_symlink() or not path.is_dir():
            raise CompanionError("Book not found or unsafe symlink")
        return path

    def select(self, identifier):
        self.book(identifier)
        save(self.home / "state.json", {"active_book": identifier})
        return {"active_book": identifier}


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def row_groups(value):
    if not isinstance(value, dict):
        return []
    groups = [(value, v) for v in value.values() if isinstance(v, list) and v]
    for child in value.values():
        if isinstance(child, dict):
            groups.extend(row_groups(child))
    return groups


def bounded_response(value, limit):
    """Fit the whole UTF-8 response, not merely the source excerpt."""
    truncated = False
    while True:
        envelope = {"result": value, "metrics": {"output_bytes": 0, "limit_bytes": limit,
                    "truncated": truncated, "token_measure": "UTF-8 bytes, not exact model tokens"}}
        for _ in range(8):
            size = len(encode(envelope).encode("utf-8")) + 1
            if envelope["metrics"]["output_bytes"] == size:
                break
            envelope["metrics"]["output_bytes"] = size
        if size <= limit:
            return encode(envelope) + "\n"
        truncated = True
        # Prefer dropping complete rows over cutting structured citation objects.
        groups = row_groups(value)
        if groups:
            parent, rows = max(groups, key=lambda pair: len(encode(pair[1])))
            rows.pop()
            if "page_offset" in parent:
                omitted = parent["page_offset"] + len(rows)
                parent["next_offset"] = min(parent["next_offset"], omitted) if parent.get("next_offset") is not None else omitted
            if "matches" in parent:
                parent["next_cursor"] = (f"{rows[-1]['chapter']}:{rows[-1]['match_end']}" if rows else None)
            continue
        if isinstance(value, dict) and isinstance(value.get("text"), str) and value["text"]:
            value["text"] = value["text"][:max(0, len(value["text"]) // 2)]
            if "start" in value:
                value["end"] = value["start"] + len(value["text"])
                value["next_offset"] = value["end"]
                if "line" in value:
                    value["end_line"] = value["line"] + value["text"][:-1].count("\n")
            continue
        value = {"error": "Result exceeds output budget; request a smaller page"}
