"""Verify non-destructive registration and portable standalone copying.
Uses temporary fake Hermes homes and the project's standard-library installer.
"""

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from support import ROOT

spec = importlib.util.spec_from_file_location("companion_installer", ROOT / "install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.environment = patch.dict("os.environ", {"READING_COMPANION_HOME": ""})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_symlink_registration_is_idempotent(self):
        target = installer.install(self.home)
        self.assertTrue(target.is_symlink())
        self.assertEqual(installer.install(self.home), target)
        self.assertTrue((self.home / "reading-companion/books/inbox").is_dir())

    def test_install_creates_custom_inbox_and_preserves_contents(self):
        private = self.home / "private data"
        installer.install(self.home, data_home=private)
        incoming = private / "books/inbox/My book.md"
        incoming.write_text("keep this upload")
        installer.install(self.home, data_home=private)
        self.assertEqual(incoming.read_text(), "keep this upload")

    def test_install_honours_existing_library_environment(self):
        private = self.home / "configured data"
        with patch.dict("os.environ", {"READING_COMPANION_HOME": str(private)}):
            installer.install(self.home)
        self.assertTrue((private / "books/inbox").is_dir())

    def test_existing_destination_never_overwritten(self):
        target = self.home / "skills/reading-companion"
        target.mkdir(parents=True)
        sentinel = target / "keep.txt"
        sentinel.write_text("existing custom skill")
        with self.assertRaises(ValueError):
            installer.install(self.home)
        self.assertEqual(sentinel.read_text(), "existing custom skill")

    def test_copied_skill_is_self_contained(self):
        target = installer.install(self.home, copy=True)
        self.assertFalse(target.is_symlink())
        self.assertTrue((target / "SKILL.md").is_file())
        process = subprocess.run([sys.executable, str(target / "scripts/companion.py"), "--home", str(self.home / "data"), "list"],
                                 cwd=self.home, capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.assertIn('"books":[]', process.stdout)

    def test_missing_profile_not_created(self):
        missing = self.home / "missing"
        with self.assertRaises(ValueError):
            installer.install(missing)
        self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()
