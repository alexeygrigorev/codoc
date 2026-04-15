"""Tests for updating cells in notebooks."""

import pytest

from .conftest import create_test_notebook, load_notebook, run_notebook_command


class TestUpdateByIndex:
    """Tests for updating cells by index."""

    def test_update_by_index(self, tmp_path):
        """Test updating a cell by index."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "old code 1", "cell_type": "code"},
            {"source": "old code 2", "cell_type": "code"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "update-index", "1", "--code", "new code"
        )

        assert returncode == 0

        nb = load_notebook(notebook_path)
        assert nb.cells[0].source == "new code"
        assert nb.cells[1].source == "old code 2"

    def test_update_index_out_of_range(self, tmp_path):
        """Test updating with an out of range index."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "x = 1", "cell_type": "code"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "update-index", "99", "--code", "new code"
        )

        assert returncode != 0
        assert "out of range" in stderr.lower()


class TestUpdateById:
    """Tests for updating cells by ID."""

    def test_update_by_id(self, tmp_path):
        """Test updating a cell by its ID."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "# @cell_id=my-cell\nold code", "cell_type": "code"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "update", "my-cell", "--code", "new code"
        )

        assert returncode == 0

        nb = load_notebook(notebook_path)
        assert "# @cell_id=my-cell" in nb.cells[0].source
        assert "new code" in nb.cells[0].source
        assert "old code" not in nb.cells[0].source

    def test_update_by_id_keeps_marker(self, tmp_path):
        """Test that update preserves the cell_id marker."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "# @cell_id=test\nx = 1", "cell_type": "code"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "update", "test", "--code", "y = 2"
        )

        assert returncode == 0

        nb = load_notebook(notebook_path)
        lines = nb.cells[0].source.split("\n")
        assert lines[0] == "# @cell_id=test"
        assert "y = 2" in nb.cells[0].source

    def test_update_by_id_not_found(self, tmp_path):
        """Test updating a non-existent cell ID."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "x = 1", "cell_type": "code"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "update", "nonexistent", "--code", "new code"
        )

        assert returncode != 0
        assert "not found" in stderr.lower()
