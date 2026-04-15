"""Tests for standalone CLI commands.

These tests use nbformat to read notebooks and verify results are 100% correct.
"""

import subprocess
import sys
from pathlib import Path

import nbformat
import pytest

NOTEBOOK_EDITOR_CMD = [sys.executable, "-m", "codoc.nb_edit"]


def load_notebook(path: Path) -> nbformat.NotebookNode:
    """Load a notebook using nbformat."""
    with open(path) as f:
        return nbformat.read(f, as_version=4)


class TestRemoveIds:
    """Tests for remove-ids command."""

    def test_remove_ids_from_notebook(self, tmp_path):
        """Test removing all cell_id markers from a notebook."""
        notebook_path = tmp_path / "test.ipynb"

        # Create a notebook with cells that have IDs
        nb = nbformat.v4.new_notebook()
        nb.cells.append(nbformat.v4.new_code_cell("# @cell_id=first\nimport os"))
        nb.cells.append(nbformat.v4.new_code_cell("# @cell_id=second\nx = 1"))
        nb.cells.append(nbformat.v4.new_code_cell("# @cell_id=third\nprint(x)"))
        nb.cells.append(nbformat.v4.new_markdown_cell("# Some markdown"))
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        # Run remove-ids command
        cmd = NOTEBOOK_EDITOR_CMD + [str(notebook_path), "remove-ids"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        assert result.returncode == 0
        assert "Removed 3 cell_id marker(s)" in result.stdout

        # Verify all cell_id markers were removed from code cells
        nb_after = load_notebook(notebook_path)
        assert "# @cell_id=first" not in nb_after.cells[0].source
        assert "# @cell_id=second" not in nb_after.cells[1].source
        assert "# @cell_id=third" not in nb_after.cells[2].source
        # Markdown cells should be unchanged
        assert nb_after.cells[3].cell_type == "markdown"
        assert "# Some markdown" in nb_after.cells[3].source

    def test_remove_ids_preserves_code_content(self, tmp_path):
        """Test that removing IDs preserves the actual code content."""
        notebook_path = tmp_path / "test.ipynb"

        nb = nbformat.v4.new_notebook()
        nb.cells.append(nbformat.v4.new_code_cell("# @cell_id=my-cell\nx = 1\ny = 2"))
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        cmd = NOTEBOOK_EDITOR_CMD + [str(notebook_path), "remove-ids"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        assert result.returncode == 0

        nb_after = load_notebook(notebook_path)
        source = nb_after.cells[0].source
        assert "x = 1" in source
        assert "y = 2" in source
        assert "# @cell_id=my-cell" not in source

    def test_remove_ids_with_blank_line_after_marker(self, tmp_path):
        """Test that blank line after cell_id marker is also removed."""
        notebook_path = tmp_path / "test.ipynb"

        nb = nbformat.v4.new_notebook()
        # Cell with blank line after marker (as added by add-id)
        cell = nbformat.v4.new_code_cell("# @cell_id=test\n\nx = 1")
        nb.cells.append(cell)
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        cmd = NOTEBOOK_EDITOR_CMD + [str(notebook_path), "remove-ids"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        assert result.returncode == 0

        nb_after = load_notebook(notebook_path)
        source = nb_after.cells[0].source
        assert "# @cell_id=test" not in source
        assert "x = 1" in source

    def test_remove_ids_empty_notebook(self, tmp_path):
        """Test remove-ids on an empty notebook."""
        notebook_path = tmp_path / "test.ipynb"

        nb = nbformat.v4.new_notebook()
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        cmd = NOTEBOOK_EDITOR_CMD + [str(notebook_path), "remove-ids"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        assert result.returncode == 0
        assert "Removed 0 cell_id marker(s)" in result.stdout

    def test_remove_ids_notebook_without_ids(self, tmp_path):
        """Test remove-ids on a notebook that has no cell_id markers."""
        notebook_path = tmp_path / "test.ipynb"

        nb = nbformat.v4.new_notebook()
        nb.cells.append(nbformat.v4.new_code_cell("import os\nx = 1"))
        nb.cells.append(nbformat.v4.new_code_cell("print(x)"))
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        cmd = NOTEBOOK_EDITOR_CMD + [str(notebook_path), "remove-ids"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        assert result.returncode == 0
        assert "Removed 0 cell_id marker(s)" in result.stdout

        nb_after = load_notebook(notebook_path)
        assert "import os" in nb_after.cells[0].source
        assert "print(x)" in nb_after.cells[1].source

    def test_remove_ids_preserves_outputs(self, tmp_path):
        """Test that removing IDs preserves cell outputs."""
        notebook_path = tmp_path / "test.ipynb"

        nb = nbformat.v4.new_notebook()
        cell = nbformat.v4.new_code_cell("# @cell_id=test\nx = 1 + 1\nprint(x)")
        cell.outputs = [
            nbformat.v4.new_output(
                output_type="stream",
                name="stdout",
                text="2\n"
            )
        ]
        cell.execution_count = 1
        nb.cells.append(cell)
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        cmd = NOTEBOOK_EDITOR_CMD + [str(notebook_path), "remove-ids"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        assert result.returncode == 0

        nb_after = load_notebook(notebook_path)
        assert len(nb_after.cells[0].outputs) == 1
        assert nb_after.cells[0].outputs[0].text == "2\n"
        assert "# @cell_id=test" not in nb_after.cells[0].source
