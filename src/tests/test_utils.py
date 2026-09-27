"""
src/tests/test_utils.py

Unit tests for shared utility functions.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from src.utils import mkdirs


class TestUtils(unittest.TestCase):

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp(prefix="cernodata_test_utils_")

    def tearDown(self) -> None:
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_mkdirs_ignores_empty_string(self) -> None:
        # Should execute cleanly without raising FileNotFoundError or ValueError
        mkdirs("")

    def test_mkdirs_ignores_none(self) -> None:
        mkdirs(None)

    def test_mkdirs_ignores_empty_pathlib_path(self) -> None:
        mkdirs(Path(""))

    def test_mkdirs_ignores_dirname_of_bare_filename(self) -> None:
        bare_filename_dir = os.path.dirname("document.pdf")
        self.assertEqual(bare_filename_dir, "")
        mkdirs(bare_filename_dir)

    def test_mkdirs_creates_valid_directory(self) -> None:
        target_path = os.path.join(self.test_dir, "nested", "output_dir")
        self.assertFalse(os.path.exists(target_path))
        mkdirs(target_path)
        self.assertTrue(os.path.isdir(target_path))

    def test_mkdirs_existing_directory_succeeds(self) -> None:
        target_path = os.path.join(self.test_dir, "existing_dir")
        os.makedirs(target_path, exist_ok=True)
        self.assertTrue(os.path.isdir(target_path))
        mkdirs(target_path, exist_ok=True)
        self.assertTrue(os.path.isdir(target_path))

    def test_mkdirs_with_pathlib_instance(self) -> None:
        target_path = Path(self.test_dir) / "from_pathlib" / "sub"
        self.assertFalse(target_path.exists())
        mkdirs(target_path)
        self.assertTrue(target_path.is_dir())
