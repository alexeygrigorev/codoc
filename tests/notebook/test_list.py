"""Tests for listing notebook cells."""

import pytest

from .conftest import create_test_notebook, run_notebook_command


class TestList:
    """Tests for listing notebook cells."""

    def test_list_empty_notebook(self, tmp_path):
        """Test listing an empty notebook."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, cells=[])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "list"
        )

        assert returncode == 0
        assert stdout == ""

    def test_list_code_cells(self, tmp_path):
        """Test listing code cells."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "print('hello')", "cell_type": "code"},
            {"source": "x = 42", "cell_type": "code"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "list"
        )

        assert returncode == 0
        assert "print('hello')" in stdout
        assert "x = 42" in stdout
        assert "[1] code" in stdout
        assert "[2] code" in stdout

    def test_list_markdown_cells(self, tmp_path):
        """Test listing markdown cells."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "# Heading", "cell_type": "markdown"},
            {"source": "print('hello')", "cell_type": "code"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "list"
        )

        assert returncode == 0
        assert "# Heading" in stdout
        assert "[1] markdown" in stdout
        assert "[2] code" in stdout

    def test_list_shows_cell_id(self, tmp_path):
        """Test that list shows cell_id markers."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "# @cell_id=my-cell\nprint('hello')", "cell_type": "code"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "list"
        )

        assert returncode == 0
        assert "# @cell_id=my-cell" in stdout
        assert "print('hello')" in stdout


class TestListLineNumbers:
    """Tests for --line-numbers flag in list command."""

    def test_line_numbers_for_code_cells(self, tmp_path):
        """Test that line numbers appear for code cells."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "x = 1\ny = 2\nz = 3", "cell_type": "code"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "list", "--line-numbers"
        )

        assert returncode == 0
        # nbformat stores source as list with trailing \n, creating blank lines
        assert "| x = 1" in stdout
        assert "| y = 2" in stdout
        assert "| z = 3" in stdout

    def test_line_numbers_not_shown_for_markdown_cells(self, tmp_path):
        """Test that line numbers do NOT appear for markdown cells."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "# Heading\nSome text", "cell_type": "markdown"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "list", "--line-numbers"
        )

        assert returncode == 0
        assert "# Heading" in stdout
        # Markdown cells should not have line number prefixes
        assert "1 | # Heading" not in stdout

    def test_line_numbers_right_aligned(self, tmp_path):
        """Test right-alignment for multi-digit line numbers."""
        # Create a cell with more than 9 lines
        lines = [f"line_{i} = {i}" for i in range(1, 12)]
        source = "\n".join(lines)
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": source, "cell_type": "code"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "list", "--line-numbers"
        )

        assert returncode == 0
        # nbformat creates extra blank lines, so total lines > 9, padding width > 1
        # Verify padding: single-digit numbers should have leading space
        assert " 1 | line_1 = 1" in stdout
        # Multi-digit numbers should not have leading space
        assert "| line_11 = 11" in stdout

    def test_default_behavior_unchanged(self, tmp_path):
        """Test that default behavior (no --line-numbers) is unchanged."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "x = 1\ny = 2", "cell_type": "code"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "list"
        )

        assert returncode == 0
        assert "x = 1" in stdout
        # Should NOT have line number prefixes
        assert "1 | x = 1" not in stdout

    def test_line_numbers_short_flag(self, tmp_path):
        """Test that -n short flag works for --line-numbers."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "x = 1\ny = 2", "cell_type": "code"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "list", "-n"
        )

        assert returncode == 0
        assert "| x = 1" in stdout
        assert "| y = 2" in stdout
