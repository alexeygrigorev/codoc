"""Shared fixtures for notebook tests."""

import subprocess
import sys
from pathlib import Path

import nbformat
import pytest

NOTEBOOK_EDITOR_CMD = [sys.executable, "-m", "codoc.nb_edit"]


@pytest.fixture
def temp_notebook(tmp_path):
    """Create a temporary notebook path."""
    return tmp_path / "test.ipynb"


def create_test_notebook(path: Path, cells: list | None = None) -> None:
    """Create a test notebook with optional cells."""
    nb = nbformat.v4.new_notebook()
    nb.metadata.kernelspec = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3"
    }

    if cells is not None:
        for cell in cells:
            if cell.get("cell_type") == "markdown":
                nb.cells.append(nbformat.v4.new_markdown_cell(cell["source"]))
            else:
                nb.cells.append(nbformat.v4.new_code_cell(cell["source"]))
    else:
        nb.cells.append(nbformat.v4.new_code_cell("print('hello')"))

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        nbformat.write(nb, f)


def load_notebook(path: Path) -> nbformat.NotebookNode:
    """Load a notebook and return it."""
    with open(path) as f:
        return nbformat.read(f, as_version=4)


def run_notebook_command(*args) -> tuple[int, str, str]:
    """Run a notebook editor command and return exit code, stdout, stderr."""
    cmd = NOTEBOOK_EDITOR_CMD + list(args)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent.parent
    )
    return result.returncode, result.stdout, result.stderr
