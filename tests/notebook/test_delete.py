"""Tests for deleting cells from notebooks."""

import pytest

from .conftest import create_test_notebook, load_notebook, run_notebook_command


class TestDeleteByIndex:
    """Tests for deleting cells by index."""

    def test_delete_by_index(self, tmp_path):
        """Test deleting a cell by index."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "first", "cell_type": "code"},
            {"source": "second", "cell_type": "code"},
            {"source": "third", "cell_type": "code"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "delete", "2"
        )

        assert returncode == 0

        nb = load_notebook(notebook_path)
        assert len(nb.cells) == 2
        assert "first" in nb.cells[0].source
        assert "third" in nb.cells[1].source

    def test_delete_first_cell(self, tmp_path):
        """Test deleting the first cell."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "first", "cell_type": "code"},
            {"source": "second", "cell_type": "code"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "delete", "1"
        )

        assert returncode == 0

        nb = load_notebook(notebook_path)
        assert len(nb.cells) == 1
        assert "second" in nb.cells[0].source

    def test_delete_last_cell(self, tmp_path):
        """Test deleting the last cell."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "first", "cell_type": "code"},
            {"source": "second", "cell_type": "code"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "delete", "2"
        )

        assert returncode == 0

        nb = load_notebook(notebook_path)
        assert len(nb.cells) == 1
        assert "first" in nb.cells[0].source

    def test_delete_index_out_of_range(self, tmp_path):
        """Test deleting with an out of range index."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "x = 1", "cell_type": "code"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "delete", "99"
        )

        assert returncode != 0
        assert "out of range" in stderr.lower()


class TestDeleteById:
    """Tests for deleting cells by ID."""

    def test_delete_by_id(self, tmp_path):
        """Test deleting a cell by its ID."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "# @cell_id=first\nx = 1", "cell_type": "code"},
            {"source": "# @cell_id=second\ny = 2", "cell_type": "code"},
            {"source": "# @cell_id=third\nz = 3", "cell_type": "code"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "delete", "second"
        )

        assert returncode == 0

        nb = load_notebook(notebook_path)
        assert len(nb.cells) == 2
        assert "first" in nb.cells[0].source
        assert "third" in nb.cells[1].source

    def test_delete_by_id_not_found(self, tmp_path):
        """Test deleting a non-existent cell ID."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "# @cell_id=first\nx = 1", "cell_type": "code"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "delete", "nonexistent"
        )

        assert returncode != 0
        assert "not found" in stderr.lower()
