"""Fast notebook editor using JSON directly.

This module provides fast notebook editing operations using JSON directly
instead of nbformat for faster operations.
"""

from codoc.nb_edit.editor import (
    FastNotebookEditor,
    NotebookDict,
    create_notebook,
    find_cell_index_by_id,
    load_notebook,
)

from codoc.nb_edit.batch import BatchCommand, BatchExecutor, parse_batch_commands
from codoc.nb_edit.cli import create_parser, run_single_command
from codoc.nb_edit.__main__ import run_cli

__all__ = [
    "FastNotebookEditor",
    "NotebookDict",
    "create_notebook",
    "find_cell_index_by_id",
    "load_notebook",
    "BatchCommand",
    "BatchExecutor",
    "parse_batch_commands",
    "create_parser",
    "run_cli",
    "run_single_command",
]

# For backward compatibility, alias FastNotebookEditor to NotebookEditor
NotebookEditor = FastNotebookEditor


def __main__():
    """Entry point for running as a module."""
    from codoc.nb_edit.__main__ import run_cli
    run_cli()
