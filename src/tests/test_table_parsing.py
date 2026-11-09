"""
src/tests/test_table_parsing.py

Unit tests for table content parsing with row and column awareness.
Exercises Markdown table parsing, Docling table data mapping, cell alignment
scoring, column-oriented views, and DOMNode table integration.
"""

import unittest
from typing import Any, List, Optional
from src.dom import BoundingBox, DOMNode, DocumentDOM
from src.parsers.table_parser import (
    ParsedTable,
    ParsedTableCell,
    TableParser,
    build_column_oriented_view,
    compute_table_alignment_score,
    generate_html_table,
    generate_markdown_table,
    is_markdown_separator_row,
    parse_column_alignments,
    parse_docling_table,
    parse_markdown_table,
    parse_table_content,
    split_markdown_row,
)
from src.parsers.docling_helpers import build_node_content
from src.quality.handlers_structural import TablesLayerHandler


class _StubTableCell:
    def __init__(
        self,
        text: str,
        column_header: bool = False,
        row_span: int = 1,
        col_span: int = 1,
        bbox: Optional[Any] = None,
    ) -> None:
        self.text = text
        self.column_header = column_header
        self.row_span = row_span
        self.col_span = col_span
        self.bbox = bbox

    def _get_text(self, doc: Any = None) -> str:
        return self.text


class _StubTableData:
    def __init__(self, grid: List[List[_StubTableCell]]) -> None:
        self.grid = grid
        self.num_rows = len(grid)
        self.num_cols = len(grid[0]) if grid else 0


class _StubTableItem:
    label = "table"

    def __init__(self, data: _StubTableData, markdown: str = "") -> None:
        self.data = data
        self._markdown = markdown

    def export_to_markdown(self, doc: Any = None) -> str:
        return self._markdown


class TestTableParsing(unittest.TestCase):
    """Test suite verifying table content parsing with row and column awareness."""

    def test_split_markdown_row_standard(self) -> None:
        row_str = "| Col 1 | Col 2 | Col 3 |"
        cells = split_markdown_row(row_str)
        self.assertEqual(cells, ["Col 1", "Col 2", "Col 3"])

    def test_split_markdown_row_no_outer_pipes(self) -> None:
        row_str = "Col 1 | Col 2 | Col 3"
        cells = split_markdown_row(row_str)
        self.assertEqual(cells, ["Col 1", "Col 2", "Col 3"])

    def test_split_markdown_row_escaped_pipes(self) -> None:
        row_str = r"| Item \| Part A | Price \| USD | Qty |"
        cells = split_markdown_row(row_str)
        self.assertEqual(cells, ["Item | Part A", "Price | USD", "Qty"])

    def test_split_markdown_row_empty_cells(self) -> None:
        row_str = "| Col 1 |  | Col 3 |"
        cells = split_markdown_row(row_str)
        self.assertEqual(cells, ["Col 1", "", "Col 3"])

    def test_separator_detection_and_alignments(self) -> None:
        sep_cells = [":---", ":---:", "---:", "---"]
        self.assertTrue(is_markdown_separator_row(sep_cells))
        alignments = parse_column_alignments(sep_cells)
        self.assertEqual(alignments, ["left", "center", "right", "default"])

        non_sep = ["Col 1", "Col 2", "Col 3"]
        self.assertFalse(is_markdown_separator_row(non_sep))

    def test_parse_markdown_table_complete(self) -> None:
        sample_md = """
        | Product | Category | Qty | Unit Price |
        | :--- | :---: | ---: | ---: |
        | Laptop | Hardware | 5 | 1200.00 |
        | Keyboard | Accessories | 15 | 75.50 |
        | Monitor | Displays | 8 | 320.00 |
        """
        table = parse_markdown_table(sample_md)

        self.assertEqual(table.num_rows, 4)
        self.assertEqual(table.num_cols, 4)
        self.assertEqual(table.headers, ["Product", "Category", "Qty", "Unit Price"])
        self.assertTrue(table.is_consistent)
        self.assertGreaterEqual(table.cell_alignment_score, 0.95)

        # Row awareness verification
        self.assertEqual(len(table.rows), 4)
        self.assertEqual(table.rows[0], ["Product", "Category", "Qty", "Unit Price"])
        self.assertEqual(table.rows[1], ["Laptop", "Hardware", "5", "1200.00"])
        self.assertEqual(table.rows[3], ["Monitor", "Displays", "8", "320.00"])
        self.assertEqual(len(table.data_rows), 3)

        # Column awareness verification
        self.assertEqual(len(table.columns), 4)
        self.assertEqual(table.columns[0], ["Product", "Laptop", "Keyboard", "Monitor"])
        self.assertEqual(table.columns[1], ["Category", "Hardware", "Accessories", "Displays"])
        self.assertEqual(table.columns[2], ["Qty", "5", "15", "8"])
        self.assertEqual(table.columns[3], ["Unit Price", "1200.00", "75.50", "320.00"])

        # Cell coordinates verification
        self.assertEqual(len(table.cells), 16)
        cell_0_0 = table.cells[0]
        self.assertEqual(cell_0_0["row_idx"], 0)
        self.assertEqual(cell_0_0["col_idx"], 0)
        self.assertEqual(cell_0_0["text"], "Product")
        self.assertTrue(cell_0_0["is_header"])

        cell_1_3 = table.grid[1][3]
        self.assertEqual(cell_1_3["row_idx"], 1)
        self.assertEqual(cell_1_3["col_idx"], 3)
        self.assertEqual(cell_1_3["text"], "1200.00")
        self.assertFalse(cell_1_3["is_header"])

    def test_parse_markdown_table_ragged_mismatched_columns(self) -> None:
        ragged_md = """
        | Header A | Header B | Header C |
        | --- | --- | --- |
        | Val 1 | Val 2 |
        | Val 3 | Val 4 | Val 5 | Val 6 |
        """
        table = parse_markdown_table(ragged_md)

        self.assertEqual(table.num_rows, 3)
        self.assertEqual(table.num_cols, 4)
        self.assertFalse(table.is_consistent)
        self.assertLess(table.cell_alignment_score, 0.90)

        # Row 1 only has 2 cells, Row 2 has 4 cells
        self.assertEqual(len(table.rows[1]), 2)
        self.assertEqual(len(table.rows[2]), 4)

        # Columns are rectangularly padded
        self.assertEqual(len(table.columns), 4)
        self.assertEqual(table.columns[2], ["Header C", "", "Val 5"])
        self.assertEqual(table.columns[3], ["", "", "Val 6"])

    def test_parse_docling_table_item(self) -> None:
        class FakeBbox:
            l = 10.0
            t = 20.0
            r = 100.0
            b = 40.0

        grid = [
            [
                _StubTableCell("Region", column_header=True, bbox=FakeBbox()),
                _StubTableCell("Revenue", column_header=True, bbox=FakeBbox()),
            ],
            [
                _StubTableCell("North", bbox=FakeBbox()),
                _StubTableCell("15000", bbox=FakeBbox()),
            ],
            [
                _StubTableCell("South", bbox=FakeBbox()),
                _StubTableCell("23000", bbox=FakeBbox()),
            ],
        ]
        data = _StubTableData(grid)
        item = _StubTableItem(data=data, markdown="| Region | Revenue |\n| --- | --- |\n| North | 15000 |\n| South | 23000 |")

        table = parse_docling_table(item, preset="docling_deep")

        self.assertEqual(table.num_rows, 3)
        self.assertEqual(table.num_cols, 2)
        self.assertEqual(table.headers, ["Region", "Revenue"])
        self.assertEqual(table.rows[1], ["North", "15000"])
        self.assertEqual(table.columns[0], ["Region", "North", "South"])
        self.assertEqual(table.columns[1], ["Revenue", "15000", "23000"])
        self.assertTrue(table.is_consistent)
        self.assertEqual(table.cell_alignment_score, 0.98)

        # Cell bounding boxes extracted
        self.assertIsNotNone(table.cells[0]["bbox"])
        assert table.cells[0]["bbox"] is not None
        self.assertEqual(table.cells[0]["bbox"]["x0"], 10.0)

    def test_build_node_content_integrates_table_content(self) -> None:
        class _StubMarkdownTableItem:
            label = "table"

            def export_to_markdown(self, doc: Any = None) -> str:
                return "| A | B |\n| --- | --- |\n| 1 | 2 |"

        item = _StubMarkdownTableItem()
        content = build_node_content(item, "table_grid", preset="docling_fast")

        self.assertIn("rows", content)
        self.assertIn("columns", content)
        self.assertIn("headers", content)
        self.assertIn("cells", content)
        self.assertIn("grid", content)
        self.assertIn("markdown_table", content)
        self.assertIn("cell_alignment_score", content)

        self.assertEqual(content["headers"], ["A", "B"])
        self.assertEqual(content["rows"], [["A", "B"], ["1", "2"]])
        self.assertEqual(content["columns"], [["A", "1"], ["B", "2"]])
        self.assertEqual(content["num_rows"], 2)
        self.assertEqual(content["num_cols"], 2)

    def test_dom_node_table_helper_properties(self) -> None:
        node = DOMNode(
            node_id="table_1",
            type="table_grid",
            global_page_index=1,
            temp_slice_index=1,
            bounding_box=BoundingBox(0.0, 0.0, 200.0, 100.0),
            content={
                "headers": ["Quarter", "Profit"],
                "rows": [["Quarter", "Profit"], ["Q1", "50k"], ["Q2", "60k"]],
                "columns": [["Quarter", "Q1", "Q2"], ["Profit", "50k", "60k"]],
                "grid": [[{"text": "Quarter"}, {"text": "Profit"}]],
            },
        )
        self.assertEqual(node.table_headers, ["Quarter", "Profit"])
        self.assertEqual(node.table_rows, [["Quarter", "Profit"], ["Q1", "50k"], ["Q2", "60k"]])
        self.assertEqual(node.table_columns, [["Quarter", "Q1", "Q2"], ["Profit", "50k", "60k"]])
        self.assertIsNotNone(node.table_grid)

        # Non-table nodes return None
        para_node = DOMNode(
            node_id="p_1",
            type="paragraph",
            global_page_index=1,
            temp_slice_index=1,
            bounding_box=BoundingBox(0.0, 0.0, 100.0, 50.0),
            content={"rows": [["a", "b"]]},
        )
        self.assertIsNone(para_node.table_rows)
        self.assertIsNone(para_node.table_columns)
        self.assertIsNone(para_node.table_headers)

    def test_tables_layer_handler_detects_violations_from_parsed_markdown(self) -> None:
        # Node with ragged markdown table without pre-computed rows
        ragged_md = "| A | B |\n| --- | --- |\n| single_col |"
        node = DOMNode(
            node_id="ragged_table_node",
            type="table_grid",
            global_page_index=1,
            temp_slice_index=1,
            bounding_box=BoundingBox(10.0, 10.0, 300.0, 200.0),
            content={"markdown_table": ragged_md},
        )
        dom = DocumentDOM(document_id="doc_t", source_filename="test.pdf", total_pages=1, nodes=[node])

        handler = TablesLayerHandler()
        violations = handler.detect_violations(dom)

        self.assertGreater(len(violations), 0)
        rule_types = {v["rule_type"] for v in violations}
        self.assertIn("table_column_count_mismatch", rule_types)

    def test_table_parser_class_and_generators(self) -> None:
        parser = TableParser(preset="docling_deep")
        md_text = "| K1 | K2 |\n| --- | --- |\n| v1 | v2 |"
        parsed = parser.parse_markdown(md_text)

        self.assertEqual(parsed.headers, ["K1", "K2"])
        self.assertEqual(parsed.num_rows, 2)
        self.assertEqual(parsed.num_cols, 2)

        gen_md = generate_markdown_table(parsed.headers, [["v1", "v2"]])
        self.assertIn("K1", gen_md)
        self.assertIn("v1", gen_md)

        gen_html = generate_html_table(parsed.headers, [["v1", "v2"]])
        self.assertIn("<table", gen_html)
        self.assertIn("<th>K1</th>", gen_html)
        self.assertIn("<td>v1</td>", gen_html)

    def test_build_column_oriented_view(self) -> None:
        rows = [["a1", "b1", "c1"], ["a2", "b2"]]
        cols = build_column_oriented_view(rows, 3)
        self.assertEqual(cols[0], ["a1", "a2"])
        self.assertEqual(cols[1], ["b1", "b2"])
        self.assertEqual(cols[2], ["c1", ""])

    def test_parsed_table_cell_model(self) -> None:
        cell = ParsedTableCell(row_idx=1, col_idx=2, text="Value", is_header=False, bbox={"x0": 5.0, "y0": 10.0, "x1": 50.0, "y1": 30.0})
        cell_dict = cell.to_dict()
        self.assertEqual(cell_dict["row_idx"], 1)
        self.assertEqual(cell_dict["col_idx"], 2)
        self.assertEqual(cell_dict["text"], "Value")
        self.assertEqual(cell_dict["bbox"]["x0"], 5.0)

    def test_parse_table_content_and_alignment_score(self) -> None:
        raw_md = "| H1 | H2 |\n| --- | --- |\n| a | b |"
        res = parse_table_content(raw_md)
        self.assertIn("rows", res)
        self.assertEqual(res["headers"], ["H1", "H2"])

        parsed_obj = TableParser().parse(raw_md)
        self.assertIsInstance(parsed_obj, ParsedTable)

        score_perfect = compute_table_alignment_score([["a", "b"], ["c", "d"]])
        self.assertEqual(score_perfect, 0.96)
        score_ragged = compute_table_alignment_score([["a", "b"], ["c"]])
        self.assertLess(score_ragged, score_perfect)


if __name__ == "__main__":
    unittest.main()
