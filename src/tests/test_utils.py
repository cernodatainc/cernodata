"""
src/tests/test_utils.py

Unit tests for shared utility functions.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from src.utils import (
    find_available_port,
    generate_document_id,
    mkdirs,
    resolve_and_validate_pdf_path,
    safe_load_json,
)


class TestUtils(unittest.TestCase):

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp(prefix="cernodata_test_utils_")

    def tearDown(self) -> None:
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_mkdirs_ignores_typical_empty_values(self) -> None:
        # Should execute cleanly without raising FileNotFoundError or ValueError
        mkdirs("")
        mkdirs(None)
        mkdirs(Path(""))

        bare_filename_dir = os.path.dirname("document.pdf")
        self.assertEqual(bare_filename_dir, "")
        mkdirs(bare_filename_dir)

    def test_mkdirs_creates_nested_directory_from_str_and_pathlib(self) -> None:
        targets = (
            os.path.join(self.test_dir, "nested", "output_dir"),
            Path(self.test_dir) / "from_pathlib" / "sub",
        )
        for target_path in targets:
            with self.subTest(type=type(target_path).__name__):
                self.assertFalse(os.path.exists(target_path))
                mkdirs(target_path)
                self.assertTrue(os.path.isdir(target_path))

    def test_mkdirs_existing_directory_succeeds(self) -> None:
        target_path = os.path.join(self.test_dir, "existing_dir")
        os.makedirs(target_path, exist_ok=True)
        self.assertTrue(os.path.isdir(target_path))
        mkdirs(target_path, exist_ok=True)
        self.assertTrue(os.path.isdir(target_path))

    def test_find_available_port(self) -> None:
        port = find_available_port(start_port=8200, max_attempts=20)
        self.assertGreaterEqual(port, 8200)

        # With 0 attempts, loop will not run and should fallback to port 0 ephemeral allocation
        fallback_port = find_available_port(start_port=8200, max_attempts=0)
        self.assertGreater(fallback_port, 0)

    def test_generate_document_id(self) -> None:
        doc_id1 = generate_document_id("sample.pdf")
        doc_id2 = generate_document_id("path/to/sample.pdf")
        self.assertTrue(doc_id1.startswith("doc_"))
        self.assertEqual(doc_id1, doc_id2)

    def test_resolve_and_validate_pdf_path(self) -> None:
        pdf_file = os.path.join(self.test_dir, "test_doc.pdf")
        with open(pdf_file, "wb") as f:
            f.write(b"%PDF-1.4 test")
        resolved = resolve_and_validate_pdf_path(pdf_file)
        self.assertEqual(resolved, pdf_file)

        with self.assertRaises(FileNotFoundError):
            resolve_and_validate_pdf_path(os.path.join(self.test_dir, "nonexistent.pdf"))

    def test_safe_load_json(self) -> None:
        json_path = Path(self.test_dir) / "data.json"
        with open(json_path, "w", encoding="utf-8") as f:
            f.write('{"key": "value"}')

        loaded = safe_load_json(json_path)
        self.assertEqual(loaded, {"key": "value"})

        missing = safe_load_json(Path(self.test_dir) / "missing.json", default={"fallback": True})
        self.assertEqual(missing, {"fallback": True})
