"""
src/quality/retrieval_sandbox.py

In-memory lexical retrieval sandbox (TASK-105).

Splits DocumentDOM nodes into chunks in reading order and ranks them against a
question with Okapi BM25, using only the standard library, so retrieval tests
(testing_decision_tree.md Section 5) run without an external vector database.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from src.dom import DOMNode, DocumentDOM
from src.dom.enums import DOMNodeType

BM25_K1 = 1.5
BM25_B = 0.75

_TOKEN_RE = re.compile(r"\w+")
_SEPARATOR = "\n"


def tokenize(text: str) -> list[str]:
    """Lowercases text and splits it into Unicode word tokens."""
    return _TOKEN_RE.findall(text.lower())


@dataclass
class IndexedChunk:
    chunk_id: str
    doc_id: str
    page_indices: list[int]
    node_ids: list[str]
    text: str
    tokens: list[str]


@dataclass
class _Piece:
    node_id: str
    page: int
    text: str


def _type_value(node: DOMNode) -> str:
    return node.type.value if isinstance(node.type, DOMNodeType) else str(node.type)


def _node_text(node: DOMNode) -> str:
    """Returns node text; tables without raw_text fall back to their row cells."""
    text = node.text.strip()
    rows = node.table_rows
    if text or rows is None:
        return text
    return _SEPARATOR.join(" | ".join(str(cell) for cell in row) for row in rows).strip()


class _ChunkBuilder:
    """Accumulates node text into chunks of at most `size` body characters for one document.

    The most recent heading is prepended to every chunk and does not count towards `size`.
    """

    def __init__(self, doc_id: str, size: int, overlap: int) -> None:
        self.doc_id = doc_id
        self.size = size
        self.overlap = overlap
        self.chunks: list[IndexedChunk] = []
        self._heading: _Piece | None = None
        self._pieces: list[_Piece] = []
        self._has_new_text = False
        self._section_emitted = False

    def start_section(self, heading: _Piece) -> None:
        self.finish_section()
        self._heading = heading

    def finish_section(self) -> None:
        """Emits pending text; a heading with no body still yields one chunk."""
        if self._has_new_text or (self._heading is not None and not self._section_emitted):
            self._emit()
        self._pieces = []
        self._has_new_text = False
        self._section_emitted = False

    def add(self, piece: _Piece, keep_intact: bool) -> None:
        if self._has_new_text and not self._fits(piece.node_id, piece.text):
            self._emit()
            self._carry_overlap()
        if keep_intact and len(piece.text) <= self.size:
            if not self._fits(piece.node_id, piece.text):
                self._pieces = []
            self._append(piece.node_id, piece.page, piece.text)
            return
        text = piece.text
        while not self._fits(piece.node_id, text):
            room = self.size - self._length() - len(self._joiner(piece.node_id))
            if room <= 0:
                self._pieces = []
                continue
            self._append(piece.node_id, piece.page, text[:room])
            text = text[room:]
            self._emit()
            self._carry_overlap()
        if text:
            self._append(piece.node_id, piece.page, text)

    def _joiner(self, node_id: str) -> str:
        """Text of one node split across pieces is rejoined without a separator."""
        if not self._pieces or self._pieces[-1].node_id == node_id:
            return ""
        return _SEPARATOR

    def _append(self, node_id: str, page: int, text: str) -> None:
        if self._pieces and self._pieces[-1].node_id == node_id:
            last = self._pieces[-1]
            self._pieces[-1] = _Piece(node_id, last.page, last.text + text)
        else:
            self._pieces.append(_Piece(node_id, page, text))
        self._has_new_text = True

    def _length(self) -> int:
        return sum(len(p.text) for p in self._pieces) + len(_SEPARATOR) * max(len(self._pieces) - 1, 0)

    def _fits(self, node_id: str, text: str) -> bool:
        return self._length() + len(self._joiner(node_id)) + len(text) <= self.size

    def _carry_overlap(self) -> None:
        """Keeps the last `overlap` characters of the emitted body as the start of the next chunk."""
        tail: list[_Piece] = []
        budget = self.overlap
        for piece in reversed(self._pieces):
            if budget <= 0:
                break
            snippet = piece.text[-budget:]
            tail.insert(0, _Piece(piece.node_id, piece.page, snippet))
            budget -= len(snippet) + len(_SEPARATOR)
        self._pieces = tail
        self._has_new_text = False

    def _emit(self) -> None:
        parts = ([self._heading] if self._heading is not None else []) + self._pieces
        text = _SEPARATOR.join(p.text for p in parts)
        self.chunks.append(IndexedChunk(
            chunk_id=f"{self.doc_id}_c{len(self.chunks)}",
            doc_id=self.doc_id,
            page_indices=sorted({p.page for p in parts}),
            node_ids=list(dict.fromkeys(p.node_id for p in parts)),
            text=text,
            tokens=tokenize(text),
        ))
        self._section_emitted = True


def _chunk_document(dom: DocumentDOM, size: int, overlap: int) -> list[IndexedChunk]:
    """Chunks dom.nodes in their stored (reading) order; each heading starts a new section."""
    builder = _ChunkBuilder(dom.document_id, size, overlap)
    for node in dom.nodes:
        text = _node_text(node)
        if not text:
            continue
        piece = _Piece(node.node_id, node.global_page_index, text)
        node_type = _type_value(node)
        if node_type == DOMNodeType.HEADING.value:
            builder.start_section(piece)
        else:
            builder.add(piece, keep_intact=node_type == DOMNodeType.TABLE_GRID.value)
    builder.finish_section()
    return builder.chunks


class LexicalRetrievalSandbox:
    """BM25 index over DocumentDOM chunks held entirely in memory."""

    def __init__(self) -> None:
        self.chunks: list[IndexedChunk] = []
        self._term_freqs: list[Counter[str]] = []
        self._doc_freqs: Counter[str] = Counter()
        self._avg_length = 0.0

    def index_documents(
        self,
        documents: list[DocumentDOM],
        chunk_size_chars: int = 1000,
        chunk_overlap_chars: int = 150,
    ) -> None:
        """Replaces the current index with chunks built from documents."""
        if chunk_size_chars < 1:
            raise ValueError(f"chunk_size_chars must be at least 1, got {chunk_size_chars}")
        if not 0 <= chunk_overlap_chars < chunk_size_chars:
            raise ValueError(
                f"chunk_overlap_chars must be in [0, chunk_size_chars), got {chunk_overlap_chars}"
            )
        self.chunks = [
            chunk for dom in documents for chunk in _chunk_document(dom, chunk_size_chars, chunk_overlap_chars)
        ]
        self._term_freqs = [Counter(chunk.tokens) for chunk in self.chunks]
        self._doc_freqs = Counter(term for freqs in self._term_freqs for term in freqs)
        total_tokens = sum(len(chunk.tokens) for chunk in self.chunks)
        self._avg_length = total_tokens / len(self.chunks) if self.chunks else 0.0

    def query(self, question: str, top_k: int = 3) -> list[tuple[IndexedChunk, float]]:
        """Returns up to top_k chunks with a positive BM25 score, best first; ties keep index order."""
        if top_k < 1:
            raise ValueError(f"top_k must be at least 1, got {top_k}")
        terms = set(tokenize(question))
        avg_length = self._avg_length or 1.0
        scored: list[tuple[IndexedChunk, float]] = []
        for chunk, freqs in zip(self.chunks, self._term_freqs):
            norm = BM25_K1 * (1.0 - BM25_B + BM25_B * len(chunk.tokens) / avg_length)
            score = sum(
                self._idf(term) * freqs[term] * (BM25_K1 + 1.0) / (freqs[term] + norm)
                for term in terms
                if term in freqs
            )
            if score > 0.0:
                scored.append((chunk, score))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:top_k]

    def _idf(self, term: str) -> float:
        """Non-negative BM25 idf: ln(1 + (N - df + 0.5) / (df + 0.5))."""
        doc_freq = self._doc_freqs[term]
        return math.log(1.0 + (len(self.chunks) - doc_freq + 0.5) / (doc_freq + 0.5))
