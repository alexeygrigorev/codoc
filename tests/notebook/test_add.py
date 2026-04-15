"""Tests for adding cells to notebooks."""

import subprocess

import pytest

from .conftest import NOTEBOOK_EDITOR_CMD, create_test_notebook, load_notebook, run_notebook_command


class TestAdd:
    """Tests for adding cells to notebooks."""

    def test_add_code_cell(self, tmp_path):
        """Test adding a code cell."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, cells=[])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "add", "--code", "x = 42"
        )

        assert returncode == 0

        nb = load_notebook(notebook_path)
        assert len(nb.cells) == 1
        assert nb.cells[0].cell_type == "code"
        assert nb.cells[0].source == "x = 42"

    def test_add_code_cell_with_id(self, tmp_path):
        """Test adding a code cell with a cell_id."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, cells=[])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "add", "--code", "x = 42", "--id", "my-cell"
        )

        assert returncode == 0

        nb = load_notebook(notebook_path)
        assert len(nb.cells) == 1
        assert nb.cells[0].source == "# @cell_id=my-cell\n\nx = 42"

    def test_add_markdown_cell(self, tmp_path):
        """Test adding a markdown cell."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, cells=[])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "add", "--markdown", "# Heading"
        )

        assert returncode == 0

        nb = load_notebook(notebook_path)
        assert len(nb.cells) == 1
        assert nb.cells[0].cell_type == "markdown"
        assert nb.cells[0].source == "# Heading"

    def test_add_from_stdin(self, tmp_path):
        """Test adding code from stdin."""
        from pathlib import Path

        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, cells=[])

        code = "def hello():\n    print('world')"

        result = subprocess.run(
            NOTEBOOK_EDITOR_CMD + [str(notebook_path), "add", "--code", "-"],
            input=code,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent
        )

        assert result.returncode == 0

        nb = load_notebook(notebook_path)
        assert "def hello():" in nb.cells[0].source
        assert "    print('world')" in nb.cells[0].source

    def test_add_with_id_includes_blank_line(self, tmp_path):
        """Test that adding with --id includes a blank line after the marker."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, cells=[])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "add", "--code", "print('hello')", "--id", "test"
        )

        assert returncode == 0

        nb = load_notebook(notebook_path)
        lines = nb.cells[0].source.split("\n")
        assert lines[0] == "# @cell_id=test"
        assert lines[1] == ""
        assert lines[2] == "print('hello')"
