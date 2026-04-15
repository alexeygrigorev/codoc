"""Tests for notebook loading."""

from .conftest import create_test_notebook, load_notebook, run_notebook_command


class TestLoad:
    """Tests for notebook loading."""

    def test_load_existing_notebook(self, tmp_path):
        """Test loading an existing notebook."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "x = 42", "cell_type": "code"}
        ])

        nb = load_notebook(notebook_path)
        assert len(nb.cells) == 1
        assert "x = 42" in nb.cells[0].source

    def test_load_preserves_cell_types(self, tmp_path):
        """Test that loading preserves cell types."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "# Heading", "cell_type": "markdown"},
            {"source": "x = 42", "cell_type": "code"},
        ])

        nb = load_notebook(notebook_path)
        assert nb.cells[0].cell_type == "markdown"
        assert nb.cells[1].cell_type == "code"
