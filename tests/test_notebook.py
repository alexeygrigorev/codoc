"""Tests for notebook loading and cell extraction."""

from pathlib import Path

import pytest

from codoc.nb_edit.editor import (
    load_notebook,
    find_cells_by_id,
    get_cell_by_id,
    get_cell_output,
    CellInfo,
    CellOutput,
)
from codoc.errors import CellNotFoundError, NotebookNotFoundError


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "notebooks"


class TestLoadNotebook:
    """Tests for load_notebook function."""

    def test_loads_valid_notebook(self):
        """It loads a valid notebook file."""
        path = FIXTURES_DIR / "sample.ipynb"
        result = load_notebook(path)

        assert result is not None
        assert hasattr(result, "cells")
        assert len(result.cells) > 0

    def test_nonexistent_file_raises_error(self):
        """It raises NotebookNotFoundError for nonexistent file."""
        with pytest.raises(NotebookNotFoundError):
            load_notebook(Path("/nonexistent/notebook.ipynb"))

    def test_preserves_cell_types(self):
        """It preserves the cell types from the notebook."""
        notebook = load_notebook(FIXTURES_DIR / "sample.ipynb")

        code_cells = [c for c in notebook.cells if c.cell_type == "code"]
        markdown_cells = [c for c in notebook.cells if c.cell_type == "markdown"]

        assert len(code_cells) > 0
        assert len(markdown_cells) > 0


class TestFindCellsById:
    """Tests for find_cells_by_id function."""

    def test_finds_cells_with_markers(self):
        """It finds all cells with @cell_id markers."""
        notebook = load_notebook(FIXTURES_DIR / "sample.ipynb")
        result = find_cells_by_id(notebook)

        assert len(result) == 4  # 4 cells with @cell_id markers
        assert "print-hello" in result
        assert "answer" in result
        assert "import-math" in result
        assert "no-output" in result

    def test_returns_cell_info_objects(self):
        """It returns CellInfo objects with correct properties."""
        notebook = load_notebook(FIXTURES_DIR / "sample.ipynb")
        result = find_cells_by_id(notebook)

        cell = result["print-hello"]

        assert isinstance(cell, CellInfo)
        assert cell.cell_id == "print-hello"
        assert cell.source == 'print("Hello, World!")'
        assert isinstance(cell.full_source, list)
        assert cell.cell_index >= 0

    def test_strips_cell_id_from_source(self):
        """It removes the @cell_id line from the source."""
        notebook = load_notebook(FIXTURES_DIR / "sample.ipynb")
        result = find_cells_by_id(notebook)

        cell = result["answer"]
        assert cell.source == "42"  # Cell_id line and blank lines removed

    def test_ignores_cells_without_markers(self):
        """It ignores cells that don't have @cell_id markers."""
        notebook = load_notebook(FIXTURES_DIR / "sample.ipynb")
        result = find_cells_by_id(notebook)

        # The last cell in sample.ipynb has no marker
        assert "unmarked-cell" not in result

    def test_ignores_markdown_cells(self):
        """It ignores markdown cells even if they have @cell_id."""
        notebook = load_notebook(FIXTURES_DIR / "sample.ipynb")
        result = find_cells_by_id(notebook)

        # The markdown cell in the fixture should not be in results
        assert all(isinstance(c, CellInfo) for c in result.values())

    def test_handles_multiline_source(self):
        """It handles cells with multiple source lines."""
        notebook = load_notebook(FIXTURES_DIR / "sample.ipynb")
        result = find_cells_by_id(notebook)

        cell = result["import-math"]
        assert "import math" in cell.source
        assert "result = math.sqrt(16)" in cell.source


class TestGetCellById:
    """Tests for get_cell_by_id function."""

    def test_gets_existing_cell(self):
        """It gets a cell by its ID."""
        notebook = load_notebook(FIXTURES_DIR / "sample.ipynb")
        result = get_cell_by_id(notebook, "print-hello", "test.ipynb")

        assert result.cell_id == "print-hello"
        assert result.source == 'print("Hello, World!")'

    def test_raises_error_for_nonexistent_cell(self):
        """It raises CellNotFoundError for nonexistent cell ID."""
        notebook = load_notebook(FIXTURES_DIR / "sample.ipynb")

        with pytest.raises(CellNotFoundError) as exc_info:
            get_cell_by_id(notebook, "nonexistent-cell", "test.ipynb")

        assert "nonexistent-cell" in str(exc_info.value)
        assert "test.ipynb" in str(exc_info.value)


class TestGetCellOutput:
    """Tests for get_cell_output function."""

    def test_gets_stream_output(self):
        """It extracts stdout output from a cell."""
        notebook = load_notebook(FIXTURES_DIR / "sample.ipynb")

        # First cell has stream output
        cell = notebook.cells[0]
        result = get_cell_output(cell)

        assert isinstance(result, CellOutput)
        assert result.has_output
        assert "Hello, World!" in result.text

    def test_gets_execute_result_output(self):
        """It extracts execute_result output from a cell."""
        notebook = load_notebook(FIXTURES_DIR / "sample.ipynb")

        # Second cell has execute_result output
        cell = notebook.cells[1]
        result = get_cell_output(cell)

        assert result.has_output
        assert "42" in result.text

    def test_handles_no_output(self):
        """It handles cells with no output."""
        notebook = load_notebook(FIXTURES_DIR / "sample.ipynb")

        # Third cell has no output
        cell = notebook.cells[2]
        result = get_cell_output(cell)

        assert not result.has_output
        assert result.text == ""

    def test_handles_multiple_outputs(self):
        """It handles cells with multiple outputs."""
        notebook = load_notebook(FIXTURES_DIR / "sample.ipynb")

        # Cell 4 has both stream output (the cell prints a list)
        cell = notebook.cells[3]
        result = get_cell_output(cell)

        assert result.has_output

    def test_trims_output_whitespace(self):
        """It trims whitespace from output."""
        notebook = load_notebook(FIXTURES_DIR / "sample.ipynb")

        cell = notebook.cells[0]
        result = get_cell_output(cell)

        # Output should be trimmed
        assert result.text == result.text.strip()


class TestCellInfo:
    """Tests for CellInfo dataclass."""

    def test_cell_info_properties(self):
        """It stores all cell information correctly."""
        info = CellInfo(
            cell_id="test-cell",
            source="x = 42",
            full_source=["# @cell_id=test-cell", "x = 42"],
            cell_index=5,
            attributes={},
        )

        assert info.cell_id == "test-cell"
        assert info.source == "x = 42"
        assert info.full_source == ["# @cell_id=test-cell", "x = 42"]
        assert info.cell_index == 5
        assert info.attributes == {}


class TestCellOutput:
    """Tests for CellOutput dataclass."""

    def test_cell_output_properties(self):
        """It stores output information correctly."""
        output = CellOutput(text="42", has_output=True)

        assert output.text == "42"
        assert output.has_output is True

    def test_cell_output_no_output(self):
        """It represents cells with no output."""
        output = CellOutput(text="", has_output=False)

        assert output.text == ""
        assert output.has_output is False
