"""
src/tests/test_retrieval_sandbox.py

Unit tests for the in-memory BM25 retrieval sandbox (TASK-105).
"""

from __future__ import annotations

import math
import unittest

from src.dom import DOMNode, DocumentDOM
from src.dom.enums import DOMNodeType
from src.quality.retrieval_sandbox import BM25_B, BM25_K1, IndexedChunk, LexicalRetrievalSandbox, tokenize
from src.tests.conftest import make_test_node


def _node(node_id: str, text: str, node_type: str = "paragraph", page: int = 1) -> DOMNode:
    return make_test_node(raw_text=text, node_id=node_id, node_type=node_type, page=page)


def _dom(doc_id: str, *nodes: DOMNode) -> DocumentDOM:
    return DocumentDOM(document_id=doc_id, source_filename=f"{doc_id}.pdf", total_pages=3, nodes=list(nodes))


def _chunks(*nodes: DOMNode, size: int = 1000, overlap: int = 0) -> list[IndexedChunk]:
    sandbox = LexicalRetrievalSandbox()
    sandbox.index_documents([_dom("d", *nodes)], chunk_size_chars=size, chunk_overlap_chars=overlap)
    return sandbox.chunks


class TokenizeTests(unittest.TestCase):
    def test_lowercases_and_keeps_unicode_words(self) -> None:
        self.assertEqual(tokenize("Ciśnienie MAX: 12,5 bar!"), ["ciśnienie", "max", "12", "5", "bar"])


class ChunkingTests(unittest.TestCase):
    def test_short_nodes_share_one_chunk_with_metadata(self) -> None:
        chunks = _chunks(_node("n1", "Alpha text", page=1), _node("n2", "Beta text", page=2))
        self.assertEqual(len(chunks), 1)
        chunk = chunks[0]
        self.assertEqual((chunk.chunk_id, chunk.doc_id), ("d_c0", "d"))
        self.assertEqual((chunk.node_ids, chunk.page_indices), (["n1", "n2"], [1, 2]))
        self.assertEqual(chunk.text, "Alpha text\nBeta text")
        self.assertEqual(chunk.tokens, ["alpha", "text", "beta", "text"])

    def test_long_text_is_split_with_overlap(self) -> None:
        text = "".join(chr(ord("a") + i % 26) for i in range(250))
        chunks = _chunks(_node("n1", text), size=100, overlap=20)
        self.assertTrue(all(len(c.text) <= 100 for c in chunks))
        for previous, current in zip(chunks, chunks[1:]):
            self.assertEqual(current.text[:20], previous.text[-20:])
        self.assertEqual(chunks[0].text + "".join(c.text[20:] for c in chunks[1:]), text)

    def test_zero_overlap_partitions_text(self) -> None:
        chunks = _chunks(_node("n1", "x" * 250), size=100, overlap=0)
        self.assertEqual([len(c.text) for c in chunks], [100, 100, 50])

    def test_most_recent_heading_is_prepended(self) -> None:
        chunks = _chunks(
            _node("p0", "Preamble"),
            _node("h1", "Installation", node_type="heading"),
            _node("p1", "a" * 60),
            _node("p2", "b" * 60),
            _node("h2", "Maintenance", node_type="heading"),
            _node("p3", "Replace the filter"),
            size=80,
        )
        self.assertEqual([c.text.split("\n")[0] for c in chunks], ["Preamble", "Installation", "Installation", "Maintenance"])
        self.assertEqual(chunks[0].node_ids, ["p0"])
        self.assertEqual(chunks[1].node_ids, ["h1", "p1"])
        self.assertEqual(chunks[3].node_ids, ["h2", "p3"])

    def test_heading_without_body_yields_chunk(self) -> None:
        chunks = _chunks(_node("h1", "Appendix", node_type="heading"))
        self.assertEqual([(c.text, c.node_ids) for c in chunks], [("Appendix", ["h1"])])

    def test_table_that_fits_is_not_split(self) -> None:
        table = "| A | B |\n| 1 | 2 |\n| 3 | 4 |"
        for overlap in (0, 30):
            with self.subTest(overlap=overlap):
                chunks = _chunks(
                    _node("p1", "p" * 60), _node("t1", table, node_type="table_grid"), size=80, overlap=overlap
                )
                self.assertEqual(len(chunks), 2)
                self.assertEqual(chunks[0].text, "p" * 60)
                self.assertTrue(chunks[1].text.endswith(table))
                self.assertEqual(chunks[1].node_ids[-1], "t1")

    def test_table_larger_than_chunk_is_split(self) -> None:
        table = "| cell |\n" * 30
        chunks = _chunks(_node("t1", table.strip(), node_type="table_grid"), size=80)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(c.text) <= 80 for c in chunks))

    def test_table_rows_used_when_raw_text_missing(self) -> None:
        node = make_test_node(
            raw_text="", node_id="t1", node_type="table_grid", extra_content={"rows": [["Model", "Power"], ["X1", "5 kW"]]}
        )
        self.assertEqual(_chunks(node)[0].text, "Model | Power\nX1 | 5 kW")

    def test_empty_nodes_and_enum_types(self) -> None:
        heading = _node("h1", "Intro")
        heading.type = DOMNodeType.HEADING
        chunks = _chunks(heading, _node("n1", "   "), _node("n2", "Body"))
        self.assertEqual([c.node_ids for c in chunks], [["h1", "n2"]])

    def test_chunk_ids_are_per_document_and_heading_does_not_leak(self) -> None:
        sandbox = LexicalRetrievalSandbox()
        sandbox.index_documents([
            _dom("a", _node("h1", "Title A", node_type="heading"), _node("n1", "First")),
            _dom("b", _node("n1", "Second")),
        ])
        self.assertEqual([(c.chunk_id, c.text) for c in sandbox.chunks], [("a_c0", "Title A\nFirst"), ("b_c0", "Second")])

    def test_invalid_parameters_raise_value_error(self) -> None:
        sandbox = LexicalRetrievalSandbox()
        invalid = {"size zero": (0, 0), "negative overlap": (100, -1), "overlap equals size": (100, 100)}
        for label, (size, overlap) in invalid.items():
            with self.subTest(label), self.assertRaises(ValueError):
                sandbox.index_documents([], chunk_size_chars=size, chunk_overlap_chars=overlap)


class QueryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sandbox = LexicalRetrievalSandbox()
        self.sandbox.index_documents([
            _dom("manual",
                 _node("h1", "Operating limits", node_type="heading"),
                 _node("n1", "The maximum operating temperature of the pump is 125 C."),
                 _node("h2", "Maintenance", node_type="heading"),
                 _node("n2", "Replace the oil filter every 500 hours of operation.")),
            _dom("brochure", _node("n1", "Our pump range covers residential and industrial use.")),
        ], chunk_size_chars=200, chunk_overlap_chars=0)

    def test_relevant_chunk_ranks_first(self) -> None:
        results = self.sandbox.query("What is the maximum temperature of the pump?")
        self.assertEqual(results[0][0].chunk_id, "manual_c0")
        scores = [score for _, score in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_top_k_limits_results(self) -> None:
        self.assertEqual(len(self.sandbox.query("pump", top_k=1)), 1)
        self.assertEqual(len(self.sandbox.query("pump", top_k=10)), 2)

    def test_no_match_or_empty_index_returns_empty(self) -> None:
        self.assertEqual(self.sandbox.query("zebra"), [])
        self.assertEqual(LexicalRetrievalSandbox().query("pump"), [])

    def test_invalid_top_k_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            self.sandbox.query("pump", top_k=0)

    def test_score_matches_bm25_formula(self) -> None:
        chunks = self.sandbox.chunks
        avg_length = sum(len(c.tokens) for c in chunks) / len(chunks)
        doc_freq = sum(1 for c in chunks if "oil" in c.tokens)
        idf = math.log(1.0 + (len(chunks) - doc_freq + 0.5) / (doc_freq + 0.5))
        target = next(c for c in chunks if "oil" in c.tokens)
        freq = target.tokens.count("oil")
        norm = BM25_K1 * (1.0 - BM25_B + BM25_B * len(target.tokens) / avg_length)
        expected = idf * freq * (BM25_K1 + 1.0) / (freq + norm)
        [(chunk, score)] = self.sandbox.query("oil oil")
        self.assertIs(chunk, target)
        self.assertAlmostEqual(score, expected)

    def test_reindexing_replaces_previous_index(self) -> None:
        self.sandbox.index_documents([_dom("other", _node("n1", "Unrelated content"))])
        self.assertEqual(self.sandbox.query("pump"), [])
        self.assertEqual([c.chunk_id for c in self.sandbox.chunks], ["other_c0"])


if __name__ == "__main__":
    unittest.main()
