"""Custom exceptions for the codoc tool."""


class CodocError(Exception):
    """Base exception for all codoc errors."""

    pass


class CellNotFoundError(CodocError):
    """Raised when a referenced @cell_id doesn't exist in the notebook."""

    def __init__(self, notebook_path: str, cell_id: str):
        self.notebook_path = notebook_path
        self.cell_id = cell_id
        super().__init__(
            f"Cell '{cell_id}' not found in notebook: {notebook_path}"
        )


class NotebookNotFoundError(CodocError):
    """Raised when a notebook file doesn't exist."""

    def __init__(self, path: str):
        self.path = path
        super().__init__(f"Notebook not found: {path}")


class ExecutionError(CodocError):
    """Raised when notebook execution fails."""

    def __init__(self, notebook_path: str, cell_id: str | None, message: str):
        self.notebook_path = notebook_path
        self.cell_id = cell_id
        self.message = message
        if cell_id:
            super().__init__(
                f"Execution failed in {notebook_path} (cell: {cell_id}): {message}"
            )
        else:
            super().__init__(f"Execution failed in {notebook_path}: {message}")


class ParseError(CodocError):
    """Raised when frontmatter or directive parsing fails."""

    def __init__(self, file_path: str, message: str):
        self.file_path = file_path
        self.message = message
        super().__init__(f"Parse error in {file_path}: {message}")


class InvalidDirectiveError(CodocError):
    """Raised when a directive has invalid syntax."""

    def __init__(self, directive: str, message: str):
        self.directive = directive
        self.message = message
        super().__init__(f"Invalid directive '{directive}': {message}")


class EmptyOutputError(CodocError):
    """Raised when @@code-output directive is used but the cell has no output."""

    def __init__(self, notebook_path: str, cell_id: str):
        self.notebook_path = notebook_path
        self.cell_id = cell_id
        super().__init__(
            f"Cell '{cell_id}' in {notebook_path} has no output. "
            f"Run the notebook first to generate output, or use @@code instead of @@code-output."
        )


class ScriptNotFoundError(CodocError):
    """Raised when a script file doesn't exist."""

    def __init__(self, path: str):
        self.path = path
        super().__init__(f"Script not found: {path}")


class BlockNotFoundError(CodocError):
    """Raised when a block ID doesn't exist in a script file."""

    def __init__(self, script_path: str, block_id: str):
        self.script_path = script_path
        self.block_id = block_id
        super().__init__(
            f"Block '{block_id}' not found in script: {script_path}"
        )


CodegenError = CodocError
