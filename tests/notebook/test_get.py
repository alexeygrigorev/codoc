"""Tests for getting notebook cells by ID."""

import pytest

from .conftest import create_test_notebook, run_notebook_command


class TestGet:
    """Tests for getting notebook cells by ID."""

    def test_get_cell_by_id(self, tmp_path):
        """Test getting a cell by its ID."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "x = 42", "cell_type": "code"},
            {"source": "# @cell_id=my-cell\nprint('hello')", "cell_type": "code"},
            {"source": "y = 100", "cell_type": "code"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "get", "my-cell"
        )

        assert returncode == 0
        assert "# @cell_id=my-cell" in stdout
        assert "print('hello')" in stdout
        assert "x = 42" not in stdout
        assert "y = 100" not in stdout

    def test_get_nonexistent_cell(self, tmp_path):
        """Test getting a cell that doesn't exist."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "x = 42", "cell_type": "code"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "get", "nonexistent"
        )

        assert returncode == 1
        assert "not found" in stderr

    def test_get_cell_with_output(self, tmp_path):
        """Test getting a cell with output."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "# @cell_id=output-cell\nprint('test output')", "cell_type": "code"},
        ])

        # Execute the notebook first to get output
        run_notebook_command(str(notebook_path), "execute")

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "get", "output-cell", "--with-output"
        )

        assert returncode == 0
        assert "# @cell_id=output-cell" in stdout
        assert "print('test output')" in stdout
        assert "test output" in stdout

    def test_get_cell_with_output_limit(self, tmp_path):
        """Test getting a cell with output limit."""
        notebook_path = tmp_path / "test.ipynb"
        # Create a cell with multi-line output
        source = "\n".join([
            "# @cell_id=multi-line",
            "for i in range(20):",
            "    print(f'line {i}')",
        ])
        create_test_notebook(notebook_path, [
            {"source": source, "cell_type": "code"},
        ])

        # Execute the notebook
        run_notebook_command(str(notebook_path), "execute")

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "get", "multi-line", "--with-output", "--limit", "5"
        )

        assert returncode == 0
        assert "line 0" in stdout
        assert "line 4" in stdout
        assert "line 15" not in stdout  # Should be limited

    def test_get_first_cell(self, tmp_path):
        """Test getting the first cell by ID."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "# @cell_id=first\nx = 1", "cell_type": "code"},
            {"source": "# @cell_id=second\ny = 2", "cell_type": "code"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "get", "first"
        )

        assert returncode == 0
        assert "# @cell_id=first" in stdout
        assert "[1] code" in stdout
        assert "x = 1" in stdout
        assert "y = 2" not in stdout

    def test_get_last_cell(self, tmp_path):
        """Test getting the last cell by ID."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "# @cell_id=first\nx = 1", "cell_type": "code"},
            {"source": "# @cell_id=last\ny = 2", "cell_type": "code"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "get", "last"
        )

        assert returncode == 0
        assert "# @cell_id=last" in stdout
        assert "[2] code" in stdout
        assert "y = 2" in stdout
        assert "x = 1" not in stdout

    def test_get_cell_without_cell_id(self, tmp_path):
        """Test that cells without @cell_id cannot be retrieved."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "x = 42", "cell_type": "code"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "get", "x"
        )

        assert returncode == 1
        assert "not found" in stderr

    def test_get_shows_cell_index(self, tmp_path):
        """Test that get shows the correct cell index."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "first = 1", "cell_type": "code"},
            {"source": "second = 2", "cell_type": "code"},
            {"source": "third = 3", "cell_type": "code"},
            {"source": "# @cell_id=target\nfound = True", "cell_type": "code"},
            {"source": "fifth = 5", "cell_type": "code"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "get", "target"
        )

        assert returncode == 0
        assert "[4] code" in stdout
