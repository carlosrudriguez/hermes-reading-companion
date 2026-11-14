"""Synthetic multilingual fixtures and temporary library helpers.
Uses only unittest-compatible standard-library temporary storage and subprocesses.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "reading-companion" / "scripts"))

from reading_companion.importing import import_book
from reading_companion.library import Book
from reading_companion.storage import Store

FRENCH = (
    "---\ntitle: La clef du jardin\nauthor: Auteur fictif\nlanguage: fr\n---\n# La clef du jardin\n"
    "## Chapitre I\nÉlise ferme la porte. Paul attend dans le jardin.\n"
    "Le vent soulève les feuilles.\n"
    "## Chapitre II\nÉlise trouve une clef. Paul lui offre une pomme.\n"
    "## Chapitre III\nOn appelle Élise Lise. Paul est son voisin.\n"
    "## Chapitre IV\nPaul et Élise marchent vers la rivière.\n"
    "## Chapitre V\nÉlise tient une corde et regarde le pont.\n"
    "Le mot « corde » désigne un assemblage de fibres tordues.\n"
    "Elle dit : « La corde est solide. »\n"
    "## Chapitre VI\nRÉVÉLATION_ZÈBRE: Paul est le gardien secret du château.\n"
    "## Chapitre VII\nÉlise et Paul ouvrent enfin la grille.\n"
)


class LibraryFixture:
    def setup_library(self):
        self.temp = tempfile.TemporaryDirectory(prefix="reading-companion-tests-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.store = Store(self.base / "library")
        self.source = self.base / "french.md"
        self.source.write_text(FRENCH, encoding="utf-8")
        import_book(self.store, self.source, "french")
        self.store.select("french")
        self.book = Book(self.store)

    def cli(self, *args, check=True):
        process = subprocess.run([sys.executable, str(ROOT / "companion.py"), "--home", str(self.store.home), *args],
                                 text=True, capture_output=True)
        if check:
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        return process, json.loads(process.stdout)
