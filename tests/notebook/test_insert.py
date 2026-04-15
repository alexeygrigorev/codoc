"""Tests for inserting cells into notebooks."""

import pytest

from .conftest import create_test_notebook, load_notebook, run_notebook_command


class TestInsertAfterIndex:
    """Tests for inserting cells after an index."""

    def test_insert_after_index(self, tmp_path):
        """Test inserting a cell after a given index."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "x = 1", "cell_type": "code"},
            {"source": "y = 2", "cell_type": "code"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "insert-after-index", "1", "--code", "z = 3"
        )

        assert returncode == 0

        nb = load_notebook(notebook_path)
        assert len(nb.cells) == 3
        assert "x = 1" in nb.cells[0].source
        assert "z = 3" in nb.cells[1].source
        assert "y = 2" in nb.cells[2].source

    def test_insert_after_index_with_id(self, tmp_path):
        """Test inserting with cell_id after an index."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "x = 1", "cell_type": "code"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "insert-after-index", "1",
            "--code", "y = 2", "--id", "new-cell"
        )

        assert returncode == 0

        nb = load_notebook(notebook_path)
        assert "# @cell_id=new-cell" in nb.cells[1].source
        assert "y = 2" in nb.cells[1].source


class TestInsertAfterId:
    """Tests for inserting cells after a cell ID."""

    def test_insert_after_id(self, tmp_path):
        """Test inserting a cell after a cell with specific ID."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "# @cell_id=first\nx = 1", "cell_type": "code"},
            {"source": "# @cell_id=second\ny = 2", "cell_type": "code"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "insert-after", "first", "--code", "middle = 1.5"
        )

        assert returncode == 0

        nb = load_notebook(notebook_path)
        assert len(nb.cells) == 3
        assert "first" in nb.cells[0].source
        assert "middle = 1.5" in nb.cells[1].source
        assert "second" in nb.cells[2].source

    def test_insert_after_id_with_id(self, tmp_path):
        """Test inserting with cell_id after another cell_id."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "# @cell_id=first\nx = 1", "cell_type": "code"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "insert-after", "first",
            "--code", "y = 2", "--id", "second"
        )

        assert returncode == 0

        nb = load_notebook(notebook_path)
        assert "# @cell_id=second" in nb.cells[1].source

    def test_insert_after_nonexistent_id(self, tmp_path):
        """Test inserting after a non-existent ID adds at the end."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "# @cell_id=first\nx = 1", "cell_type": "code"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "insert-after", "nonexistent", "--code", "y = 2"
        )

        assert returncode == 0

        nb = load_notebook(notebook_path)
        assert len(nb.cells) == 2
        assert "y = 2" in nb.cells[1].source
