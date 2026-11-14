"""Launch the portable Hermes reading companion without installing a package.
Depends only on the adjacent reading_companion package and Python 3.10+.
"""

from reading_companion.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
