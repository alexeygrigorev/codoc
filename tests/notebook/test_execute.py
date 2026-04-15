"""Tests for notebook execution."""

import pytest

from .conftest import create_test_notebook, load_notebook, run_notebook_command


class TestExecute:
    """Tests for notebook execution."""

    def test_execute_notebook(self, tmp_path):
        """Test executing a notebook and saving outputs."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "x = 1 + 1\nprint(x)", "cell_type": "code"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "execute"
        )

        assert returncode == 0
        assert "Executing notebook" in stdout
        assert "Executed and saved" in stdout

        nb = load_notebook(notebook_path)
        assert len(nb.cells) == 1
        outputs = nb.cells[0].get("outputs", [])
        assert len(outputs) > 0
        # Check that output contains the result
        output_text = "".join(
            out.get("text", "")
            for out in outputs
            if out.get("output_type") == "stream"
        )
        assert "2" in output_text

    def test_execute_with_custom_kernel(self, tmp_path):
        """Test executing with a custom kernel name."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "result = 42", "cell_type": "code"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "execute", "--kernel", "python3"
        )

        assert returncode == 0
        assert "python3" in stdout

    def test_execute_multiple_cells(self, tmp_path):
        """Test executing a notebook with multiple cells."""
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "x = 10", "cell_type": "code"},
            {"source": "y = x * 2\nprint(y)", "cell_type": "code"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "execute"
        )

        assert returncode == 0

        nb = load_notebook(notebook_path)
        assert len(nb.cells) == 2

        # Second cell should have output
        outputs = nb.cells[1].get("outputs", [])
        output_text = "".join(
            out.get("text", "")
            for out in outputs
            if out.get("output_type") == "stream"
        )
        assert "20" in output_text

    def test_execute_can_import_local_module(self, tmp_path):
        """Test that executing a notebook can import Python files from the same directory."""
        # Create a local Python module
        local_module_path = tmp_path / "my_local_module.py"
        local_module_path.write_text("""
def get_test_value():
    return "test-value-123"
""")

        # Create a notebook that imports the local module
        notebook_path = tmp_path / "test.ipynb"
        create_test_notebook(notebook_path, [
            {"source": "from my_local_module import get_test_value\nresult = get_test_value()\nprint(result)", "cell_type": "code"},
        ])

        returncode, stdout, stderr = run_notebook_command(
            str(notebook_path), "execute"
        )

        # Should succeed without import errors
        if returncode != 0:
            print(f"STDOUT: {stdout}")
            print(f"STDERR: {stderr}")
        assert returncode == 0, f"Execution failed:\nstdout:\n{stdout}\nstderr:\n{stderr}"
        assert "Executing notebook" in stdout
        assert "Executed and saved" in stdout

        # Check that the notebook executed successfully and has the expected output
        nb = load_notebook(notebook_path)
        assert len(nb.cells) == 1
        outputs = nb.cells[0].get("outputs", [])

        # Should have output with the test value
        output_text = "".join(
            out.get("text", "")
            for out in outputs
            if out.get("output_type") == "stream"
        )
        assert "test-value-123" in output_text
