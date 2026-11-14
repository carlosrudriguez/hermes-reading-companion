"""Convenient repository entry point for the portable companion CLI.
Resolves the bundled source relative to this file rather than the working directory.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "skills" / "reading-companion" / "scripts"))

from reading_companion.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
