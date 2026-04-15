"""Execute Jupyter notebooks to validate them and capture outputs."""

import asyncio
import sys
import tempfile
from pathlib import Path

# Suppress Windows zmq warning about proactor event loop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import nbformat
from nbconvert.preprocessors import ExecutePreprocessor
from nbformat import NotebookNode

from codoc.errors import ExecutionError, NotebookNotFoundError
from codoc.nb_edit.editor import find_cells_by_id


def load_notebook_for_execution(path: Path) -> NotebookNode:
    """
    Load a notebook using nbformat (for execution purposes).

    The nbformat library is needed for notebook execution
    with nbconvert. This function loads in that format.

    Args:
        path: Path to the .ipynb file

    Returns:
        NotebookNode for use with nbconvert
    """
    path = Path(path)
    if not path.exists():
        raise NotebookNotFoundError(str(path))

    try:
        return nbformat.read(path, as_version=4)
    except Exception as e:
        raise NotebookNotFoundError(f"Failed to load notebook: {e}")


def validate_notebook(
    notebook_path: Path, timeout: int = 30, kernel_name: str = "python3"
) -> NotebookNode:
    """
    Execute a notebook to validate it runs successfully.

    Args:
        notebook_path: Path to the notebook file
        timeout: Timeout in seconds for each cell
        kernel_name: Jupyter kernel name to use

    Returns:
        The executed notebook with outputs

    Raises:
        ExecutionError: If execution fails
    """
    notebook = load_notebook_for_execution(notebook_path)

    # Create an executor preprocessor
    executor = ExecutePreprocessor(
        timeout=timeout,
        kernel_name=kernel_name,
        allow_errors=False,  # Stop on first error
    )

    try:
        # Execute the notebook in a temp directory
        with tempfile.TemporaryDirectory() as tmpdir:
            executed_notebook, _ = executor.preprocess(notebook, {"metadata": {"path": tmpdir}})

        return executed_notebook

    except Exception as e:
        # Try to extract more information about which cell failed
        error_msg = str(e)
        raise ExecutionError(
            notebook_path=str(notebook_path),
            cell_id=None,
            message=error_msg,
        )


def validate_notebook_for_cells(
    notebook_path: Path, cell_ids: list[str], timeout: int = 30, kernel_name: str = "python3"
) -> NotebookNode:
    """
    Execute a notebook and verify that specific cells exist and run successfully.

    Args:
        notebook_path: Path to the notebook file
        cell_ids: List of cell IDs that must exist and execute
        timeout: Timeout in seconds for each cell
        kernel_name: Jupyter kernel name to use

    Returns:
        The executed notebook with outputs

    Raises:
        ExecutionError: If execution fails or a cell is not found
    """
    # First load without executing to check cell IDs exist
    notebook = load_notebook_for_execution(notebook_path)
    cells = find_cells_by_id(notebook)

    missing = [cell_id for cell_id in cell_ids if cell_id not in cells]
    if missing:
        raise ExecutionError(
            notebook_path=str(notebook_path),
            cell_id=None,
            message=f"Required cells not found: {', '.join(missing)}",
        )

    # Now execute to validate
    return validate_notebook(notebook_path, timeout=timeout, kernel_name=kernel_name)
