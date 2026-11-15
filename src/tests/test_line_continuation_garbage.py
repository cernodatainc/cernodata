"""Tests: valid dashes, ellipses and line-continuation fragments must not count as garbage."""

from __future__ import annotations

import unittest

from src.quality.garbage import compute_garbage_ratio


class TestLineContinuationNotGarbage(unittest.TestCase):
    def test_valid_texts(self) -> None:
        samples = [
            "Alpha beta - gamma",
            "-th alpha, beta",
            "...alpha beta",
            "alpha beta...",
            "alpha beta st-",
            "-h",
            "st-",
            "...th",
            "alpha beta \u2026",
        ]
        for text in samples:
            with self.subTest(text=text):
                self.assertEqual(compute_garbage_ratio(text), 0.0)

    def test_fragments_in_the_middle_still_flagged(self) -> None:
        self.assertGreater(compute_garbage_ratio("alpha -h beta gamma"), 0.0)
        self.assertGreater(compute_garbage_ratio("alpha beta ,, gamma"), 0.0)

    def test_damaged_sample_still_flagged(self) -> None:
        self.assertGreater(compute_garbage_ratio("Oplata zgodna z taryfa oc   )  ch h)"), 0.05)


if __name__ == "__main__":
    unittest.main()
