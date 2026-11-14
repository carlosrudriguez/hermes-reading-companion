"""Register this project's skill without altering Hermes configuration.
Uses standard-library symlinks for development or an explicit portable copy.
"""

import argparse
import os
import shutil
from pathlib import Path


def library_home(hermes_home, override=None):
    return Path(override or os.environ.get("READING_COMPANION_HOME") or Path(hermes_home).expanduser() / "reading-companion").expanduser().resolve()


def install(hermes_home, copy=False, data_home=None):
    source = Path(__file__).resolve().parent / "skills" / "reading-companion"
    root = Path(hermes_home).expanduser()
    if not root.is_dir():
        raise ValueError("Hermes home does not exist; supply the correct existing --hermes-home")
    target = root / "skills" / "reading-companion"
    already_linked = target.is_symlink() and target.resolve() == source and not copy
    if not already_linked and (target.exists() or target.is_symlink()):
        raise ValueError("Skill destination exists; inspect it before replacing anything")
    if not already_linked:
        target.parent.mkdir(parents=True, exist_ok=True)
        if copy:
            shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            target.symlink_to(source, target_is_directory=True)
    private = library_home(root, data_home)
    private.mkdir(parents=True, exist_ok=True, mode=0o700)
    (private / "books" / "inbox").mkdir(parents=True, exist_ok=True, mode=0o700)
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hermes-home", default=os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))
    parser.add_argument("--copy", action="store_true", help="Copy the whole skill instead of creating a development symlink")
    parser.add_argument("--library-home", help="Create the inbox in a custom private reading home")
    args = parser.parse_args()
    try:
        print(f"Skill: {install(args.hermes_home, args.copy, args.library_home)}")
        print(f"Book inbox: {library_home(args.hermes_home, args.library_home) / 'books' / 'inbox'}")
        print("Place a Markdown book there, then ask Hermes: Import my book from the reading-companion inbox.")
        if args.library_home:
            print("For a custom library, set READING_COMPANION_HOME in Hermes's terminal environment to this same path.")
    except (ValueError, OSError) as error:
        parser.exit(1, f"Installation stopped: {error}\n")
