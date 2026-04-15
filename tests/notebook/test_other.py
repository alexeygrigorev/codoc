"""Tests for other notebook operations (rename, add-id, etc.)."""

import pytest

from .conftest import create_test_notebook, load_notebook, run_notebook_command


class TestRenameId:
    """Tests for renaming cell IDs."""

    def test_rename_id(self, tmp_path):
        """Test renaming a cell ID."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "# @cell_id=old-name\nx = 1", "cell_type": "code"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "rename", "old-name", "--new-id", "new-name"
        )

        assert returncode == 0

        nb = load_notebook(notebook_path)
        assert "# @cell_id=new-name" in nb.cells[0].source
        assert "old-name" not in nb.cells[0].source
        assert "x = 1" in nb.cells[0].source

    def test_rename_id_not_found(self, tmp_path):
        """Test renaming a non-existent cell ID."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "x = 1", "cell_type": "code"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "rename", "nonexistent", "--new-id", "new-name"
        )

        assert returncode != 0
        assert "not found" in stderr.lower()


class TestAddId:
    """Tests for adding cell_id markers to existing cells."""

    def test_add_id_to_cell_by_index(self, tmp_path):
        """Test adding a cell_id to a cell that doesn't have one."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "x = 42", "cell_type": "code"},
            {"source": "y = 100", "cell_type": "code"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "add-id", "2", "my-cell"
        )

        assert returncode == 0

        nb = load_notebook(notebook_path)
        assert "# @cell_id=my-cell" in nb.cells[1].source
        assert "y = 100" in nb.cells[1].source
        assert nb.cells[0].source == "x = 42"

    def test_add_id_to_first_cell(self, tmp_path):
        """Test adding a cell_id to the first cell."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "first", "cell_type": "code"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "add-id", "1", "first-cell"
        )

        assert returncode == 0

        nb = load_notebook(notebook_path)
        assert "# @cell_id=first-cell" in nb.cells[0].source

    def test_add_id_to_cell_with_existing_id(self, tmp_path):
        """Test that add-id replaces an existing cell_id."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "# @cell_id=old-id\nx = 1", "cell_type": "code"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "add-id", "1", "new-id"
        )

        assert returncode == 0

        nb = load_notebook(notebook_path)
        assert "# @cell_id=new-id" in nb.cells[0].source
        assert "old-id" not in nb.cells[0].source

    def test_add_id_index_out_of_range(self, tmp_path):
        """Test add-id with out of range index."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "x = 1", "cell_type": "code"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "add-id", "99", "my-cell"
        )

        assert returncode != 0
        assert "out of range" in stderr.lower()

    def test_add_id_adds_blank_line_after_marker(self, tmp_path):
        """Test that add-id adds a blank line after the cell_id marker."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {
                "source": "answer = rag('how do I patch KDE under BSD?', output_format=AnswerResponse)\nanswer.has_answer()",
                "cell_type": "code"
            },
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "add-id", "1", "test-answer-response"
        )

        assert returncode == 0

        nb = load_notebook(notebook_path)
        source = nb.cells[0].source

        # Check the format has a blank line after cell_id
        # Should be: "# @cell_id=test-answer-response\n\nanswer = ..."
        # which when split gives ["# @cell_id=test-answer-response", "", "answer = ..."]
        lines = source.split("\n") if isinstance(source, str) else source
        assert lines[0] == "# @cell_id=test-answer-response"
        assert lines[1] == "", f"Expected blank line at index 1, got: {lines[1]!r}"
        assert "answer = rag" in lines[2]

    def test_add_id_preserves_blank_line_when_replacing(self, tmp_path):
        """Test that add-id preserves blank line when replacing existing cell_id."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {
                "source": "# @cell_id=old-id\n\nanswer = rag('test')",
                "cell_type": "code"
            },
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "add-id", "1", "new-id"
        )

        assert returncode == 0

        nb = load_notebook(notebook_path)
        source = nb.cells[0].source

        lines = source.split("\n") if isinstance(source, str) else source
        assert lines[0] == "# @cell_id=new-id"
        assert lines[1] == "", f"Expected blank line at index 1, got: {lines[1]!r}"
        assert "answer = rag" in lines[2]
